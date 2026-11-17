from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from accounts.models import UserProfile
from vendor.models import Restaurant, FoodItem, Category
from customer.cart import Cart
from orders.models import Order, SubOrder, OrderItem
from orders.serializers import CheckoutSerializer
from unittest.mock import patch

User = get_user_model()

class CheckoutAPITests(APITestCase):
    def setUp(self):
        # 1. Create test customer
        self.customer = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="password123",
            first_name="Test",
            last_name="Customer"
        )
        
        # Update profile directly in DB
        UserProfile.objects.filter(user=self.customer).update(
            address_line_1="104, Rajwada Chowk",
            city="Indore",
            state="Madhya Pradesh",
            country="India",
            pincode="452002",
            latitude="22.7533",
            longitude="75.8937"
        )
        self.customer = User.objects.get(pk=self.customer.pk)

        # 2. Create test vendor, category, and food item
        self.vendor_user = User.objects.create_user(
            username="testvendor",
            email="vendor@example.com",
            password="password123",
            first_name="Test",
            last_name="Vendor"
        )
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Nimadi Bhojan",
            is_open=True
        )
        
        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name="Main Course"
        )

        self.food_item = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Dal Baati",
            price=290.00,
            is_available=True
        )

        self.url = reverse('order-checkout')

    def test_checkout_success(self):
        """Test successful multi-vendor order placement from cart."""
        self.client.force_authenticate(user=self.customer)

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        cart = Cart(DummyRequest(self.customer))
        cart.clear()
        cart.add(self.food_item, quantity=2)

        response = self.client.post(self.url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("order_id", response.data)
        self.assertEqual(float(response.data['total_price']), 580.00)
        self.assertEqual(len(response.data['sub_orders']), 1)

    def test_checkout_empty_cart(self):
        """Test checkout failure when cart is empty."""
        self.client.force_authenticate(user=self.customer)

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        cart = Cart(DummyRequest(self.customer))
        cart.clear()

        response = self.client.post(self.url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], "Your cart is empty!")

    def test_checkout_incomplete_profile_address(self):
        """Test checkout failure when profile address is missing required fields."""
        self.client.force_authenticate(user=self.customer)
        UserProfile.objects.filter(user=self.customer).update(city="")

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        cart = Cart(DummyRequest(self.customer))
        cart.clear()
        cart.add(self.food_item, quantity=1)

        response = self.client.post(self.url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Delivery address is incomplete", response.data['error'])

    def test_checkout_missing_profile(self):
        """Test checkout failure when user profile does not exist."""
        UserProfile.objects.filter(user=self.customer).delete()
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(self.url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], "Customer profile not found. Please complete your profile first.")

    def test_checkout_invalid_cart_item(self):
        """Test checkout failure when cart item lacks restaurant reference."""
        self.client.force_authenticate(user=self.customer)

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        cart = Cart(DummyRequest(self.customer))
        cart.clear()
        cart.cart[str(self.food_item.id)] = {
            'quantity': 1,
            'price': str(self.food_item.price),
            'name': self.food_item.name,
            'restaurant_id': None
        }
        cart.save()

        response = self.client.post(self.url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid cart item data", response.data['error'])

    def test_checkout_geodjango_exception_fallback(self):
        """Test graceful fallback when GeoDjango Point coordinates are invalid (covers ValueError/TypeError)."""
        self.client.force_authenticate(user=self.customer)
        # Set invalid non-numeric latitude/longitude to trigger GeoDjango conversion exception
        UserProfile.objects.filter(user=self.customer).update(latitude="invalid_lat", longitude="invalid_lng")

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        cart = Cart(DummyRequest(self.customer))
        cart.clear()
        cart.add(self.food_item, quantity=1)

        response = self.client.post(self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch('orders.views.Order.objects.create', side_effect=Exception("Database error"))
    def test_checkout_server_error_500(self, mock_create):
        """Test 500 internal server error handling during transaction atomic block."""
        self.client.force_authenticate(user=self.customer)

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        cart = Cart(DummyRequest(self.customer))
        cart.clear()
        cart.add(self.food_item, quantity=1)

        response = self.client.post(self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("Order placement failed", response.data['error'])

    def test_unauthenticated_checkout(self):
        """Test that unauthenticated requests are blocked."""
        response = self.client.post(self.url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_models_str_and_serializers(self):
        """Test models __str__ methods (including deleted food item) and CheckoutSerializer coverage."""
        # 1. Test Serializer
        serializer = CheckoutSerializer(data={'delivery_address': 'Indore', 'latitude': 22.75, 'longitude': 75.89})
        self.assertTrue(serializer.is_valid())

        # 2. Test Order __str__
        order = Order.objects.create(
            customer=self.customer,
            total_price=290.00,
            delivery_address="Indore",
            status='PENDING'
        )
        self.assertIn("Order #", str(order))

        # 3. Test SubOrder __str__
        sub_order = SubOrder.objects.create(
            order=order,
            vendor=self.restaurant,
            suborder_total=290.00,
            status='PENDING'
        )
        self.assertIn("SubOrder #", str(sub_order))

        # 4. Test OrderItem __str__ with active food item and deleted (null) food item
        item_with_food = OrderItem.objects.create(
            sub_order=sub_order,
            food_item=self.food_item,
            quantity=1,
            price=290.00
        )
        self.assertIn("Dal Baati", str(item_with_food))

        item_deleted_food = OrderItem.objects.create(
            sub_order=sub_order,
            food_item=None,
            quantity=1,
            price=290.00
        )
        self.assertIn("Deleted Item", str(item_deleted_food))