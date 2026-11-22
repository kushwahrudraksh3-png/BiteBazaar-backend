import razorpay
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos import Point
from decimal import Decimal

from orders.models import Order, SubOrder, OrderItem
from vendor.models import Restaurant, FoodItem
from customer.cart import Cart

import hmac
import hashlib


class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # 1. Payment Method Validation
        payment_method = request.data.get('payment_method', 'UPI') # 'UPI' or 'CASH'
        if payment_method not in ['UPI', 'CASH']:
            return Response(
                {"error": "Invalid payment method. Choose either 'UPI' or 'CASH'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Fetch customer profile for auto-populated delivery address
        try:
            profile = user.userprofile
        except ObjectDoesNotExist:
            return Response(
                {
                    "error": "Customer profile not found. Please complete your profile first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not profile.address_line_1 or not profile.city or not profile.pincode:
            return Response(
                {
                    "error": "Delivery address is incomplete in your profile. Please update it before checkout."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        delivery_address = f"{profile.address_line_1}, {profile.address_line_2 or ''}, {profile.city}, {profile.state} - {profile.pincode}, {profile.country}"

        delivery_location = None
        if profile.latitude and profile.longitude:
            try:
                delivery_location = Point(
                    float(profile.longitude), float(profile.latitude), srid=4326
                )
            except (ValueError, TypeError):
                pass

        # 3. Fetch items from Redis Cart
        cart = Cart(request)
        cart_items = cart.get_cart_items()

        if not cart_items:
            return Response(
                {"error": "Your cart is empty!"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Pre-Checkout Validation & Database Price Verification (Anti-Tampering)
        vendor_cart_map = {}

        for item in cart_items:
            food_item_id = item.get("food_item_id")
            restaurant_id = item.get("restaurant_id")
            quantity = item.get("quantity")

            if not food_item_id or not restaurant_id or not quantity:
                return Response(
                    {"error": "Invalid cart item data: missing required references."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            restaurant = get_object_or_404(Restaurant, id=restaurant_id)
            if not restaurant.is_open:
                return Response(
                    {
                        "error": f"Restaurant '{restaurant.restaurant_name}' is currently closed. Cannot process checkout."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            food_item = get_object_or_404(FoodItem, id=food_item_id)
            if not food_item.is_available:
                return Response(
                    {
                        "error": f"Item '{food_item.name}' is currently out of stock or unavailable."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            verified_price = food_item.price

            if restaurant_id not in vendor_cart_map:
                vendor_cart_map[restaurant_id] = {"restaurant": restaurant, "items": []}

            vendor_cart_map[restaurant_id]["items"].append(
                {"food_item": food_item, "quantity": quantity, "price": verified_price}
            )

        try:
            with transaction.atomic():
                # 5. Financial Breakdown Calculation
                item_total = sum(
                    sum(item["price"] * item["quantity"] for item in data["items"])
                    for data in vendor_cart_map.values()
                )
                
                restaurant_gst = item_total * Decimal('0.05')  # 5% Standard GST on food
                delivery_fee = Decimal('30.00')                # Fixed standard delivery charge
                platform_fee = Decimal('5.00')                 # BiteBazaar platform fee
                
                grand_total = item_total + restaurant_gst + delivery_fee + platform_fee

                # 6. Create Master Order with Financial & Payment Fields
                order = Order.objects.create(
                    customer=user,
                    item_total=item_total,
                    restaurant_gst=restaurant_gst,
                    delivery_fee=delivery_fee,
                    platform_fee=platform_fee,
                    total_price=grand_total,
                    payment_method=payment_method,
                    payment_status='COD' if payment_method == 'CASH' else 'PENDING',
                    status='CONFIRMED' if payment_method == 'CASH' else 'PENDING',
                    delivery_address=delivery_address,
                    delivery_location=delivery_location,
                )

                sub_orders_summary = []

                # 7. Create SubOrders & OrderItems with Commission Snapshots
                for restaurant_id, data in vendor_cart_map.items():
                    restaurant = data["restaurant"]
                    items = data["items"]

                    subtotal = sum(item["price"] * item["quantity"] for item in items)
                    
                    # Commission Calculation based on restaurant's percentage
                    commission_rate = restaurant.commission_percentage / Decimal('100.0')
                    admin_commission = subtotal * commission_rate
                    vendor_payout = subtotal - admin_commission

                    sub_order = SubOrder.objects.create(
                        order=order,
                        vendor=restaurant,
                        suborder_total=subtotal,
                        admin_commission=admin_commission,
                        vendor_payout=vendor_payout,
                        status='CONFIRMED' if payment_method == 'CASH' else 'PENDING',
                    )

                    for item in items:
                        OrderItem.objects.create(
                            sub_order=sub_order,
                            food_item=item["food_item"],
                            quantity=item["quantity"],
                            price=item["price"],
                        )

                    sub_orders_summary.append(
                        {
                            "sub_order_id": sub_order.id,
                            "vendor_name": restaurant.restaurant_name,
                            "subtotal": subtotal,
                        }
                    )

                # 8. Handle Razorpay Order Creation if UPI is selected
                razorpay_order_response = None
                if payment_method == 'UPI':
                    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                    
                    # Amount in paise (e.g., ₹500 -> 50000 paise)
                    razorpay_amount = int(grand_total * 100)
                    
                    rzp_order_data = {
                        "amount": razorpay_amount,
                        "currency": "INR",
                        "receipt": f"order_rcpt_{order.id}",
                        "payment_capture": 1
                    }
                    
                    rzp_order = client.order.create(data=rzp_order_data)
                    
                    # Save razorpay order id to our master order
                    order.razorpay_order_id = rzp_order['id']
                    order.save()

                    razorpay_order_response = {
                        "razorpay_order_id": rzp_order['id'],
                        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                        "amount": razorpay_amount,
                        "currency": "INR"
                    }

                # 9. Clear Redis Cart after successful order initiation
                cart.clear()

            # 10. Return Response based on payment method
            response_data = {
                "message": "Order placed successfully!" if payment_method == 'CASH' else "Order initialized. Proceed to payment.",
                "order_id": order.id,
                "payment_method": payment_method,
                "item_total": item_total,
                "restaurant_gst": restaurant_gst,
                "delivery_fee": delivery_fee,
                "platform_fee": platform_fee,
                "total_price": grand_total,
                "sub_orders": sub_orders_summary,
            }

            if razorpay_order_response:
                response_data.update(razorpay_order_response)

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Order placement failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class VerifyPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')

        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return Response(
                {"error": "Missing required payment verification parameters."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found for the given Razorpay order ID."},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.payment_status == 'PAID':
            return Response(
                {"message": "Payment already verified and order is confirmed."},
                status=status.HTTP_200_OK
            )

        # Cryptographic Signature Verification (HMAC-SHA256)
        message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
        secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')
        generated_signature = hmac.new(secret, message, hashlib.sha256).hexdigest()

        if hmac.compare_digest(generated_signature, razorpay_signature):
            with transaction.atomic():
                order.payment_status = 'PAID'
                order.razorpay_payment_id = razorpay_payment_id
                order.razorpay_signature = razorpay_signature
                order.status = 'ACCEPTED'
                order.save()

                # Associated SubOrders ka status bhi update kar do
                order.sub_orders.all().update(status='ACCEPTED')

            return Response({
                "message": "Payment verified successfully and order confirmed!",
                "order_id": order.id,
                "payment_status": order.payment_status,
                "order_status": order.status
            }, status=status.HTTP_200_OK)
        else:
            order.payment_status = 'FAILED'
            order.status = 'CANCELLED'
            order.save()

            return Response(
                {"error": "Payment verification failed. Invalid signature."},
                status=status.HTTP_400_BAD_REQUEST
            )