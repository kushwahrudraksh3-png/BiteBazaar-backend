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
        try:
            profile = user.userprofile
        except ObjectDoesNotExist:
            return Response(
                {"error": "Customer profile not found. Please complete your profile first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate mandatory address fields
        if not profile.address_line_1 or not profile.city or not profile.pincode:
            return Response(
                {"error": "Delivery address is incomplete in your profile. Please update it before checkout."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build formatted delivery address string
        delivery_address = f"{profile.address_line_1}, {profile.address_line_2 or ''}, {profile.city}, {profile.state} - {profile.pincode}, {profile.country}"

        # Create GeoDjango Point if lat/lng are available (Longitude first in PostGIS)
        delivery_location = None
        if profile.latitude and profile.longitude:
            try:
                delivery_location = Point(float(profile.longitude), float(profile.latitude), srid=4326)
            except (ValueError, TypeError):
                pass

        # 2. Fetch items from Redis Cart using customer's Cart helper
        cart = Cart(request)
        cart_items = cart.get_cart_items()

        if not cart_items:
            return Response(
                {"error": "Your cart is empty!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Group cart items vendor-wise (Restaurant-wise split)
        vendor_cart_map = {}
        for item in cart_items:
            restaurant_id = item.get('restaurant_id')
            if not restaurant_id:
                return Response(
                    {"error": "Invalid cart item data: missing restaurant reference."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if restaurant_id not in vendor_cart_map:
                vendor_cart_map[restaurant_id] = []
            vendor_cart_map[restaurant_id].append(item)

        try:
            # 4. Atomic Transaction for Database Consistency (All-or-Nothing)
            with transaction.atomic():
                grand_total = sum(
                    sum(item['price'] * item['quantity'] for item in items)
                    for items in vendor_cart_map.values()
                )

                # Create Master Order
                master_order = Order.objects.create(
                    customer=user,
                    total_price=grand_total,
                    delivery_address=delivery_address,
                    delivery_location=delivery_location,
                    status='PENDING'
                )

                sub_orders_summary = []

                # Create SubOrders & OrderItems for each Vendor
                for restaurant_id, items in vendor_cart_map.items():
                    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
                    
                    subtotal = sum(item['price'] * item['quantity'] for item in items)

                    sub_order = SubOrder.objects.create(
                        order=master_order,
                        vendor=restaurant,
                        suborder_total=subtotal,
                        status='PENDING'
                    )

                    for item in items:
                        food_item = get_object_or_404(FoodItem, id=item['food_item_id'])
                        
                        OrderItem.objects.create(
                            sub_order=sub_order,
                            food_item=food_item,
                            quantity=item['quantity'],
                            price=item['price']  # Price snapshot at the time of order placement
                        )

                    sub_orders_summary.append({
                        "sub_order_id": sub_order.id,
                        "vendor_name": restaurant.restaurant_name,
                        "subtotal": subtotal
                    })

                # 5. Clear Redis Cart upon successful order creation
                cart.clear()

            return Response({
                "message": "Order placed successfully!",
                "order_id": master_order.id,
                "total_price": grand_total,
                "sub_orders": sub_orders_summary
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Order placement failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )