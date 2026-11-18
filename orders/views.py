from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos import Point

from orders.models import Order, SubOrder, OrderItem
from vendor.models import Restaurant, FoodItem
from customer.cart import Cart  # Customer app ke andar ka cart helper import


class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # 1. Fetch customer profile for auto-populated delivery address
        # 1. Fetch customer profile for auto-populated delivery address
        try:
            profile = user.userprofile
        except ObjectDoesNotExist:
            return Response(
                {
                    "error": "Customer profile not found. Please complete your profile first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate mandatory address fields (Make sure all required fields are checked explicitly)
        if not profile.address_line_1 or not profile.city or not profile.pincode:
            return Response(
                {
                    "error": "Delivery address is incomplete in your profile. Please update it before checkout."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build formatted delivery address string
        delivery_address = f"{profile.address_line_1}, {profile.address_line_2 or ''}, {profile.city}, {profile.state} - {profile.pincode}, {profile.country}"

        # Create GeoDjango Point if lat/lng are available (Longitude first in PostGIS)
        delivery_location = None
        if profile.latitude and profile.longitude:
            try:
                delivery_location = Point(
                    float(profile.longitude), float(profile.latitude), srid=4326
                )
            except (ValueError, TypeError):
                pass

        # 2. Fetch items from Redis Cart
        cart = Cart(request)
        cart_items = cart.get_cart_items()

        if not cart_items:
            return Response(
                {"error": "Your cart is empty!"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Pre-Checkout Validation, Vendor Grouping & Database Price Verification (Anti-Tampering)
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

            # Guard 1: Fetch Restaurant and verify it's open
            restaurant = get_object_or_404(Restaurant, id=restaurant_id)
            if not restaurant.is_open:
                return Response(
                    {
                        "error": f"Restaurant '{restaurant.restaurant_name}' is currently closed. Cannot process checkout."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Guard 2: Fetch FoodItem and check stock/availability
            food_item = get_object_or_404(FoodItem, id=food_item_id)
            if not food_item.is_available:
                return Response(
                    {
                        "error": f"Item '{food_item.name}' is currently out of stock or unavailable."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Guard 3: Use official database price to prevent client-side price tampering
            verified_price = food_item.price

            if restaurant_id not in vendor_cart_map:
                vendor_cart_map[restaurant_id] = {"restaurant": restaurant, "items": []}

            vendor_cart_map[restaurant_id]["items"].append(
                {"food_item": food_item, "quantity": quantity, "price": verified_price}
            )

        try:
            # 4. Atomic Transaction for Database Consistency (All-or-Nothing)
            with transaction.atomic():
                # Calculate Grand Total from verified database prices
                grand_total = sum(
                    sum(item["price"] * item["quantity"] for item in data["items"])
                    for data in vendor_cart_map.values()
                )

                # Create Master Order (PENDING status for payment gateway integration)
                master_order = Order.objects.create(
                    customer=user,
                    total_price=grand_total,
                    delivery_address=delivery_address,
                    delivery_location=delivery_location,
                    status="PENDING",
                )

                sub_orders_summary = []

                # Create SubOrders & OrderItems for each Vendor
                for restaurant_id, data in vendor_cart_map.items():
                    restaurant = data["restaurant"]
                    items = data["items"]

                    subtotal = sum(item["price"] * item["quantity"] for item in items)

                    sub_order = SubOrder.objects.create(
                        order=master_order,
                        vendor=restaurant,
                        suborder_total=subtotal,
                        status="PENDING",
                    )

                    for item in items:
                        OrderItem.objects.create(
                            sub_order=sub_order,
                            food_item=item["food_item"],
                            quantity=item["quantity"],
                            price=item["price"],  # Secure database price snapshot
                        )

                    sub_orders_summary.append(
                        {
                            "sub_order_id": sub_order.id,
                            "vendor_name": restaurant.restaurant_name,
                            "subtotal": subtotal,
                        }
                    )

                # 5. Clear Redis Cart upon successful order creation intent
                cart.clear()

            return Response(
                {
                    "message": "Order placed successfully (Pending Payment)!",
                    "order_id": master_order.id,
                    "total_price": grand_total,
                    "sub_orders": sub_orders_summary,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": f"Order placement failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
