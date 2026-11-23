import hmac
import hashlib
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock

from django.urls import reverse
from django.test import override_settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from vendor.models import Restaurant, FoodItem, Category
from customer.cart import Cart
from orders.models import Order, SubOrder, OrderItem
from orders.serializers import CheckoutSerializer

from django.core import mail
from orders.utils import generate_invoice_pdf, send_order_receipt_email

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


@override_settings(
    RAZORPAY_KEY_ID="rzp_test_mock_key",
    RAZORPAY_KEY_SECRET="mock_secret_key_12345",
)
class CheckoutAPITests(APITestCase):
    def setUp(self):
        # 1. Create test customer
        self.customer = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="password123",
            first_name="Test",
            last_name="Customer",
        )

        # Update profile directly in DB
        UserProfile.objects.filter(user=self.customer).update(
            address_line_1="104, Rajwada Chowk",
            city="Indore",
            state="Madhya Pradesh",
            country="India",
            pincode="452002",
            latitude="22.7533",
            longitude="75.8937",
        )
        self.customer = User.objects.get(pk=self.customer.pk)
        self.profile = self.customer.userprofile

        # 2. Create test vendor, category, and food item
        self.vendor_user = User.objects.create_user(
            username="testvendor",
            email="vendor@example.com",
            password="password123",
            first_name="Test",
            last_name="Vendor",
        )
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Nimadi Bhojan",
            is_open=True,
        )

        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name="Main Course",
        )

        self.food_item = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Dal Baati",
            price=Decimal("290.00"),
            is_available=True,
        )

        self.url = reverse("order-checkout")

    def authenticate_customer(self):
        self.client.force_authenticate(user=self.customer)

    def _setup_cart(self, quantity=2):
        cart = Cart(DummyRequest(self.customer))
        cart.clear()
        if quantity > 0:
            cart.add(self.food_item, quantity=quantity)
        return cart

    @patch("orders.views.razorpay.Client")
    def test_checkout_upi_success(self, mock_rzp_cls):
        """Test successful UPI order placement with financial breakdown and Razorpay order creation."""
        self.authenticate_customer()
        self._setup_cart(quantity=2)  # 2 * 290 = 580.00

        mock_rzp_client = MagicMock()
        mock_rzp_client.order.create.return_value = {"id": "order_rzp_test_123"}
        mock_rzp_cls.return_value = mock_rzp_client

        response = self.client.post(self.url, {"payment_method": "UPI"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Order initialized. Proceed to payment.")
        self.assertIn("order_id", response.data)
        self.assertEqual(Decimal(str(response.data["item_total"])), Decimal("580.00"))
        self.assertEqual(Decimal(str(response.data["restaurant_gst"])), Decimal("29.00"))  # 5% of 580
        self.assertEqual(Decimal(str(response.data["delivery_fee"])), Decimal("30.00"))
        self.assertEqual(Decimal(str(response.data["platform_fee"])), Decimal("5.00"))
        self.assertEqual(Decimal(str(response.data["total_price"])), Decimal("644.00"))
        self.assertEqual(len(response.data["sub_orders"]), 1)

        # Razorpay fields check
        self.assertEqual(response.data["razorpay_order_id"], "order_rzp_test_123")
        self.assertEqual(response.data["razorpay_key_id"], "rzp_test_mock_key")
        self.assertEqual(response.data["amount"], 64400)  # 644.00 * 100 paise
        self.assertEqual(response.data["currency"], "INR")

        # DB check
        order = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(order.payment_status, "PENDING")
        self.assertEqual(order.status, "PENDING")
        self.assertEqual(order.razorpay_order_id, "order_rzp_test_123")
        mock_rzp_client.order.create.assert_called_once()

    @patch("orders.views.razorpay.Client")
    def test_checkout_cash_success(self, mock_rzp_cls):
        """Test successful CASH (COD) order placement without calling Razorpay."""
        self.authenticate_customer()
        self._setup_cart(quantity=1)  # 290.00

        response = self.client.post(self.url, {"payment_method": "CASH"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Order placed successfully!")
        self.assertNotIn("razorpay_order_id", response.data)

        order = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(order.payment_method, "CASH")
        self.assertEqual(order.payment_status, "COD")
        self.assertEqual(order.status, "CONFIRMED")

        sub_order = SubOrder.objects.get(order=order)
        self.assertEqual(sub_order.status, "CONFIRMED")
        mock_rzp_cls.assert_not_called()

    def test_checkout_invalid_payment_method(self):
        """Test checkout failure when an unsupported payment method is provided."""
        self.authenticate_customer()
        response = self.client.post(self.url, {"payment_method": "CRYPTO"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid payment method", response.data["error"])

    def test_checkout_empty_cart(self):
        """Test checkout failure when cart is empty."""
        self.authenticate_customer()
        self._setup_cart(quantity=0)

        response = self.client.post(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Your cart is empty!")

    def test_checkout_incomplete_profile_address(self):
        """Test checkout failure when profile address is missing required fields."""
        self.authenticate_customer()
        UserProfile.objects.filter(user=self.customer).update(city="")
        self.customer.userprofile.refresh_from_db()
        self._setup_cart(quantity=1)

        response = self.client.post(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Delivery address is incomplete", response.data["error"])

    def test_checkout_missing_profile(self):
        """Test checkout failure when user profile does not exist."""
        self.authenticate_customer()

        with patch.object(
            type(self.customer), "userprofile", new_callable=PropertyMock
        ) as mock_profile:
            mock_profile.side_effect = UserProfile.DoesNotExist("Profile not found")
            self._setup_cart(quantity=1)

            response = self.client.post(self.url, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(
                response.data["error"],
                "Customer profile not found. Please complete your profile first.",
            )

    def test_checkout_invalid_cart_item(self):
        """Test checkout failure when cart item lacks restaurant reference."""
        self.authenticate_customer()
        cart = Cart(DummyRequest(self.customer))
        cart.clear()
        cart.cart[str(self.food_item.id)] = {
            "quantity": 1,
            "price": str(self.food_item.price),
            "name": self.food_item.name,
            "restaurant_id": None,
        }
        cart.save()

        response = self.client.post(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid cart item data", response.data["error"])

    @patch("orders.views.razorpay.Client")
    def test_checkout_geodjango_exception_fallback(self, mock_rzp_cls):
        """Test graceful fallback when GeoDjango Point coordinates raise ValueError or TypeError."""
        self.authenticate_customer()
        UserProfile.objects.filter(user=self.customer).update(
            latitude="invalid_lat",
            longitude="75.8937",
        )
        self.customer.userprofile.refresh_from_db()
        self._setup_cart(quantity=1)

        mock_rzp_client = MagicMock()
        mock_rzp_client.order.create.return_value = {"id": "order_rzp_geo_123"}
        mock_rzp_cls.return_value = mock_rzp_client

        response = self.client.post(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=response.data["order_id"])
        self.assertIsNone(order.delivery_location)

    @patch("orders.views.razorpay.Client")
    def test_checkout_razorpay_exception_500_and_rollback(self, mock_rzp_cls):
        """Test 500 error handling and transaction rollback when Razorpay API fails."""
        self.authenticate_customer()
        self._setup_cart(quantity=1)

        mock_rzp_client = MagicMock()
        mock_rzp_client.order.create.side_effect = Exception("Razorpay Gateway Error")
        mock_rzp_cls.return_value = mock_rzp_client

        response = self.client.post(self.url, {"payment_method": "UPI"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("Order placement failed", response.data["error"])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(SubOrder.objects.count(), 0)

    def test_unauthenticated_checkout(self):
        """Test that unauthenticated requests are blocked."""
        response = self.client.post(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_checkout_fails_restaurant_closed(self):
        """Test checkout failure when restaurant is closed (is_open=False guard)."""
        self.restaurant.is_open = False
        self.restaurant.save()
        self.authenticate_customer()
        self._setup_cart(quantity=1)

        response = self.client.post(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("currently closed", response.data["error"])

    def test_checkout_fails_food_item_unavailable(self):
        """Test checkout failure when food item is out of stock (is_available=False guard)."""
        self.food_item.is_available = False
        self.food_item.save()
        self.authenticate_customer()
        self._setup_cart(quantity=1)

        response = self.client.post(self.url, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("out of stock", response.data["error"])

    def test_models_str_and_serializers(self):
        """Test models __str__ methods (including deleted food item) and CheckoutSerializer coverage."""
        serializer = CheckoutSerializer(
            data={"delivery_address": "Indore", "latitude": 22.75, "longitude": 75.89}
        )
        self.assertTrue(serializer.is_valid())

        order = Order.objects.create(
            customer=self.customer,
            total_price=290.00,
            delivery_address="Indore",
            status="PENDING",
        )
        self.assertIn("Order #", str(order))

        sub_order = SubOrder.objects.create(
            order=order,
            vendor=self.restaurant,
            suborder_total=290.00,
            status="PENDING",
        )
        self.assertIn("SubOrder #", str(sub_order))

        item_with_food = OrderItem.objects.create(
            sub_order=sub_order,
            food_item=self.food_item,
            quantity=1,
            price=290.00,
        )
        self.assertIn("Dal Baati", str(item_with_food))

        item_deleted_food = OrderItem.objects.create(
            sub_order=sub_order,
            food_item=None,
            quantity=1,
            price=290.00,
        )
        self.assertIn("Deleted Item", str(item_deleted_food))


@override_settings(
    RAZORPAY_KEY_ID="rzp_test_mock_key",
    RAZORPAY_KEY_SECRET="mock_secret_key_12345",
)
class VerifyPaymentAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="verifycustomer",
            email="verifycustomer@example.com",
            password="password123",
            first_name="Verify",
            last_name="Customer",
        )
        self.vendor_user = User.objects.create_user(
            username="verifyvendor",
            email="verifyvendor@example.com",
            password="password123",
            first_name="Verify",
            last_name="Vendor",
        )
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Rajaram Dhaba",
            is_open=True,
        )
        self.verify_url = reverse("verify-payment")
        self.client.force_authenticate(user=self.customer)

    def _generate_valid_signature(self, order_id, payment_id):
        message = f"{order_id}|{payment_id}".encode("utf-8")
        secret = b"mock_secret_key_12345"
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    def test_verify_payment_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.verify_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_payment_missing_parameters(self):
        response = self.client.post(
            self.verify_url,
            {"razorpay_order_id": "order_123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Missing required payment verification parameters", response.data["error"])

    def test_verify_payment_order_not_found(self):
        response = self.client.post(
            self.verify_url,
            {
                "razorpay_order_id": "order_does_not_exist",
                "razorpay_payment_id": "pay_123",
                "razorpay_signature": "sig_123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("Order not found", response.data["error"])

    def test_verify_payment_already_paid(self):
        Order.objects.create(
            customer=self.customer,
            razorpay_order_id="order_already_paid_123",
            payment_status="PAID",
            status="ACCEPTED",
            delivery_address="Indore",
        )
        response = self.client.post(
            self.verify_url,
            {
                "razorpay_order_id": "order_already_paid_123",
                "razorpay_payment_id": "pay_123",
                "razorpay_signature": "any_sig",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Payment already verified", response.data["message"])


    def test_verify_payment_invalid_signature_fails(self):
        order = Order.objects.create(
            customer=self.customer,
            razorpay_order_id="order_tampered_999",
            payment_status="PENDING",
            status="PENDING",
            delivery_address="Indore",
        )

        response = self.client.post(
            self.verify_url,
            {
                "razorpay_order_id": "order_tampered_999",
                "razorpay_payment_id": "pay_fake_999",
                "razorpay_signature": "invalid_signature_hash",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid signature", response.data["error"])

        order.refresh_from_db()
        self.assertEqual(order.payment_status, "FAILED")
        self.assertEqual(order.status, "CANCELLED")
        
    @patch("orders.views.send_order_receipt_email")
    def test_verify_payment_valid_signature_success(self, mock_send_email):
        order = Order.objects.create(
            customer=self.customer,
            razorpay_order_id="order_valid_999",
            payment_status="PENDING",
            status="PENDING",
            delivery_address="Indore",
        )
        sub_order = SubOrder.objects.create(
            order=order,
            vendor=self.restaurant,
            suborder_total=Decimal("300.00"),
            status="PENDING",
        )

        payment_id = "pay_valid_999"
        valid_sig = self._generate_valid_signature("order_valid_999", payment_id)

        response = self.client.post(
            self.verify_url,
            {
                "razorpay_order_id": "order_valid_999",
                "razorpay_payment_id": payment_id,
                "razorpay_signature": valid_sig,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_status"], "PAID")
        self.assertEqual(response.data["order_status"], "ACCEPTED")

        order.refresh_from_db()
        sub_order.refresh_from_db()
        self.assertEqual(order.payment_status, "PAID")
        self.assertEqual(order.status, "ACCEPTED")
        self.assertEqual(order.razorpay_payment_id, payment_id)
        self.assertEqual(order.razorpay_signature, valid_sig)
        self.assertEqual(sub_order.status, "ACCEPTED")
        mock_send_email.assert_called_once_with(order)

    @patch("orders.views.send_order_receipt_email", side_effect=Exception("SMTP Down"))
    def test_verify_payment_email_failure_does_not_break_verification(self, mock_send_email):
        """Agar email bhejte waqt SMTP error aaye, tab bhi payment verify aur order confirm hona chahiye."""
        order = Order.objects.create(
            customer=self.customer,
            razorpay_order_id="order_smtp_fail_999",
            payment_status="PENDING",
            status="PENDING",
            delivery_address="Indore",
        )

        payment_id = "pay_smtp_999"
        valid_sig = self._generate_valid_signature("order_smtp_fail_999", payment_id)

        response = self.client.post(
            self.verify_url,
            {
                "razorpay_order_id": "order_smtp_fail_999",
                "razorpay_payment_id": payment_id,
                "razorpay_signature": valid_sig,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "PAID")
        self.assertEqual(order.status, "ACCEPTED")
        mock_send_email.assert_called_once_with(order)
        


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@bitebazaar.com",
)
class InvoiceAndEmailUtilsTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="pdfcustomer",
            email="pdfcustomer@example.com",
            password="password123",
            first_name="Rudraksh",
            last_name="Kushwah",
        )
        self.vendor_user = User.objects.create_user(
            username="pdfvendor",
            email="pdfvendor@example.com",
            password="password123",
            first_name="Vendor",
            last_name="User",
        )
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Nimadi Bhojan",
            is_open=True,
        )
        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name="Main Course",
        )
        self.food_item = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Dal Baati",
            price=Decimal("200.00"),
            is_available=True,
        )
        self.order = Order.objects.create(
            customer=self.customer,
            item_total=Decimal("400.00"),
            restaurant_gst=Decimal("20.00"),
            delivery_fee=Decimal("30.00"),
            platform_fee=Decimal("5.00"),
            total_price=Decimal("455.00"),
            payment_method="UPI",
            payment_status="PAID",
            razorpay_payment_id="pay_test_pdf_123",
            status="ACCEPTED",
            delivery_address="104, Rajwada Chowk, Indore",
        )
        self.sub_order = SubOrder.objects.create(
            order=self.order,
            vendor=self.restaurant,
            suborder_total=Decimal("400.00"),
            status="ACCEPTED",
        )
        OrderItem.objects.create(
            sub_order=self.sub_order,
            food_item=self.food_item,
            quantity=2,
            price=Decimal("200.00"),
        )
        # Deleted food item edge case
        OrderItem.objects.create(
            sub_order=self.sub_order,
            food_item=None,
            quantity=1,
            price=Decimal("50.00"),
        )

    def test_generate_invoice_pdf_success(self):
        """Valid PDF bytes generate hone chahiye (normal aur deleted item dono ke saath)."""
        pdf_bytes = generate_invoice_pdf(self.order)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    @patch("orders.utils.pisa.CreatePDF")
    def test_generate_invoice_pdf_error_returns_none(self, mock_create_pdf):
        """Agar xhtml2pdf error return kare, toh None aana chahiye."""
        mock_create_pdf.return_value = MagicMock(err=1)
        pdf_bytes = generate_invoice_pdf(self.order)
        self.assertIsNone(pdf_bytes)

    def test_send_order_receipt_email_success(self):
        """Email outbox mein PDF attachment ke saath send hona chahiye."""
        result = send_order_receipt_email(self.order)
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ["pdfcustomer@example.com"])
        self.assertIn(f"Order #{self.order.id}", sent_email.subject)
        self.assertEqual(len(sent_email.attachments), 1)

        filename, content, mimetype = sent_email.attachments[0]
        self.assertEqual(filename, f"BiteBazaar_Invoice_Order_{self.order.id}.pdf")
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF"))

    @patch("orders.utils.generate_invoice_pdf", return_value=None)
    def test_send_order_receipt_email_fails_when_pdf_is_none(self, mock_pdf):
        """Agar PDF generation fail ho, toh email nahi jana chahiye aur False return ho."""
        result = send_order_receipt_email(self.order)
        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)
        


class VendorOrderFlowAPITests(APITestCase):
    def setUp(self):
        # 1. Customer
        self.customer = User.objects.create_user(
            username="flowcustomer",
            email="flowcustomer@example.com",
            password="password123",
            first_name="Flow",
            last_name="Customer",
        )

        # 2. Vendor 1 (Main Restaurant)
        self.vendor_user = User.objects.create_user(
            username="flowvendor1",
            email="flowvendor1@example.com",
            password="password123",
            first_name="Vendor",
            last_name="One",
        )
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Malwa Kitchen",
            fssai_license_number="FSSAI100000001",
            is_open=True,
        )
        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name="Main Course",
        )
        self.food_item = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Poha Jalebi",
            price=Decimal("100.00"),
            is_available=True,
        )

        # 3. Vendor 2 (Other Restaurant - Ownership isolation check ke liye)
        self.other_vendor_user = User.objects.create_user(
            username="flowvendor2",
            email="flowvendor2@example.com",
            password="password123",
            first_name="Vendor",
            last_name="Two",
        )
        self.other_restaurant = Restaurant.objects.create(
            user=self.other_vendor_user,
            restaurant_name="Indori Zaika",
            is_open=True,
        )

        # 4. Orders & SubOrders
        self.order = Order.objects.create(
            customer=self.customer,
            total_price=Decimal("250.00"),
            payment_method="CASH",
            payment_status="COD",
            status="CONFIRMED",
            delivery_address="Vijay Nagar, Indore",
        )
        self.sub_order = SubOrder.objects.create(
            order=self.order,
            vendor=self.restaurant,
            suborder_total=Decimal("200.00"),
            status="CONFIRMED",
        )
        OrderItem.objects.create(
            sub_order=self.sub_order,
            food_item=self.food_item,
            quantity=2,
            price=Decimal("100.00"),
        )
        # Deleted food item coverage in OrderItemSerializer
        OrderItem.objects.create(
            sub_order=self.sub_order,
            food_item=None,
            quantity=1,
            price=Decimal("50.00"),
        )

        # Other vendor's sub_order
        self.other_order = Order.objects.create(
            customer=self.customer,
            total_price=Decimal("150.00"),
            payment_method="UPI",
            payment_status="PAID",
            status="ACCEPTED",
            delivery_address="Palasia, Indore",
        )
        self.other_sub_order = SubOrder.objects.create(
            order=self.other_order,
            vendor=self.other_restaurant,
            suborder_total=Decimal("150.00"),
            status="ACCEPTED",
        )

        self.list_url = reverse("vendor-order-list")

    def _status_url(self, sub_order_id):
        return reverse(
            "vendor-suborder-status-update",
            kwargs={"sub_order_id": sub_order_id},
        )

    # --- LIST API TESTS ---

    def test_vendor_list_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_vendor_list_forbidden_for_non_vendor(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("No restaurant associated", response.data["error"])

    def test_vendor_list_returns_only_own_orders_and_nested_items(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.sub_order.id)
        self.assertEqual(response.data[0]["customer_email"], "flowcustomer@example.com")

        item_names = [item["food_item_name"] for item in response.data[0]["items"]]
        self.assertIn("Poha Jalebi", item_names)
        self.assertIn("Deleted Item", item_names)

    def test_vendor_list_status_filter(self):
        self.client.force_authenticate(user=self.vendor_user)

        res_match = self.client.get(f"{self.list_url}?status=confirmed")
        self.assertEqual(res_match.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_match.data), 1)

        res_empty = self.client.get(f"{self.list_url}?status=PREPARING")
        self.assertEqual(res_empty.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_empty.data), 0)

    # --- STATUS UPDATE (PATCH) API TESTS ---

    def test_status_update_unauthenticated(self):
        response = self.client.patch(
            self._status_url(self.sub_order.id), {"status": "ACCEPTED"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_update_forbidden_for_non_vendor(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.patch(
            self._status_url(self.sub_order.id), {"status": "ACCEPTED"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_status_update_other_vendor_suborder_returns_404(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.patch(
            self._status_url(self.other_sub_order.id),
            {"status": "PREPARING"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_update_missing_status_field(self):
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.patch(
            self._status_url(self.sub_order.id), {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Status field is required", response.data["error"])

    def test_status_update_invalid_transition(self):
        self.client.force_authenticate(user=self.vendor_user)
        # CONFIRMED -> READY_FOR_PICKUP direct jump allowed nahi hai
        response = self.client.patch(
            self._status_url(self.sub_order.id),
            {"status": "READY_FOR_PICKUP"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid status transition", response.data["error"])
        self.assertEqual(response.data["allowed_transitions"], ["ACCEPTED", "REJECTED"])

    def test_status_update_full_kitchen_flow_and_master_sync(self):
        """CONFIRMED -> ACCEPTED -> PREPARING -> READY_FOR_PICKUP + master order sync."""
        self.client.force_authenticate(user=self.vendor_user)

        # 1. CONFIRMED -> ACCEPTED
        res1 = self.client.patch(
            self._status_url(self.sub_order.id), {"status": "ACCEPTED"}, format="json"
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data["sub_order_status"], "ACCEPTED")
        self.assertEqual(res1.data["master_order_status"], "ACCEPTED")

        # 2. ACCEPTED -> PREPARING
        res2 = self.client.patch(
            self._status_url(self.sub_order.id), {"status": "PREPARING"}, format="json"
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["sub_order_status"], "PREPARING")
        self.assertEqual(res2.data["master_order_status"], "PREPARING")

        # 3. PREPARING -> READY_FOR_PICKUP
        res3 = self.client.patch(
            self._status_url(self.sub_order.id),
            {"status": "READY_FOR_PICKUP"},
            format="json",
        )
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(res3.data["sub_order_status"], "READY_FOR_PICKUP")
        self.assertEqual(res3.data["master_order_status"], "READY_FOR_PICKUP")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "READY_FOR_PICKUP")

    def test_status_update_rejected_syncs_master_order(self):
        """CONFIRMED -> REJECTED hone par master order bhi REJECTED hona chahiye."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.patch(
            self._status_url(self.sub_order.id), {"status": "REJECTED"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sub_order_status"], "REJECTED")
        self.assertEqual(response.data["master_order_status"], "REJECTED")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "REJECTED")
        