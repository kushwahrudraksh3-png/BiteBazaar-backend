from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from vendor.models import Restaurant, Category, FoodItem
from django.shortcuts import get_object_or_404
from .permissions import IsCustomer
from . serializers import CustomerRestaurantListSerializer, CustomerCategorySerializer, CustomerProfileSerializer
from .cart import Cart
from accounts.models import UserProfile


class RestaurantListView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, formate=None):
        restaurants = Restaurant.objects.all().order_by('-id')
        serializer = CustomerRestaurantListSerializer(restaurants, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RestaurantMenuView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, restaurant_id, format=None):
        # 1. Pehle check karo ki ye restaurant ID sach mein exist karti bhi hai ya nahi
        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        
        # 2. Uss restaurant ki saari categories uthao
        categories = Category.objects.filter(restaurant=restaurant)
        
        # 3. Categories ko serialize karo (food items nested serializer apne aap le aayega)
        serializer = CustomerCategorySerializer(categories, many=True)
        
        # 4. Mast custom response return karo jisme restaurant ka naam bhi ho
        return Response({
            "restaurant_name": restaurant.restaurant_name,
            "menu": serializer.data
        }, status=status.HTTP_200_OK)
        
        
class CartView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get(self, request, format=None):
        
        cart = Cart(request)
        
        return Response({
            "cart_items": cart.cart,
            "total_price": cart.get_total_price()
        }, status=status.HTTP_200_OK)
        
    
    def post(self, request, format=None):
        cart = Cart(request)
        
        # Frontend/Postman se food_id aur quantity aayegi
        food_id = request.data.get('food_id')
        quantity = int(request.data.get('quantity', 1))
        update_quantity = request.data.get('update_quantity', False)
        
        if not food_id:
            return Response({"error": "food_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check karo item exist karta hai ya nahi
        food_item = get_object_or_404(FoodItem, id=food_id)
        
        # Available nahi hai toh throw error
        if not food_item.is_available:
            return Response({"error": "This item is currently unavailable."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Cart class ka add method call karo
        cart.add(food_item=food_item, quantity=quantity, update_quantity=update_quantity)
        
        return Response({
            "message": f"{food_item.name} added to cart.",
            "cart_items": cart.cart,
            "total_price": cart.get_total_price()
        }, status=status.HTTP_200_OK)
        
    
    def delete(self, request, format=None):
        cart = Cart(request)
        
        # DELETE request mein hum request.data se food_id nikalenge
        food_id = request.data.get('food_id')
        
        if not food_id:
            return Response({"error": "food_id is required to remove an item."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check karo item database mein hai ya nahi
        food_item = get_object_or_404(FoodItem, id=food_id)
        
        # Cart class ka remove method call karo
        cart.remove(food_item)  
        
        return Response({
            "message": f"{food_item.name} removed from cart.",
            "cart_items": cart.cart,
            "total_price": cart.get_total_price()
        }, status=status.HTTP_200_OK)
        
        
    def patch(self, request, format=None):
        
        cart = Cart(request)
        
        food_id = request.data.get('food_id')
        quantity = request.data.get('quantity')
        
        if not food_id or quantity is None:
            return Response({"error": "food_id and quantity both are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        
        # Validation: Quantity proper number hona chahiye aur 0 se bada hona chahiye
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return Response({"error": "Quantity must be greater than 0. If you want to remove the item, use DELETE method."}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"error": "Quantity must be a valid number."}, status=status.HTTP_400_BAD_REQUEST)
        
        food_item = get_object_or_404(FoodItem, id=food_id)
        
        # Yahan hum update_quantity=True bhej rahe hain taaki pichli quantity overwrite ho jaye
        cart.add(food_item=food_item, quantity=quantity, update_quantity=True)
        
        return Response({
            "message": f"Quantity for {food_item.name} updated to {quantity}.",
            "cart_items": cart.cart,
            "total_price": cart.get_total_price()
        }, status=status.HTTP_200_OK)
        



class CustomerProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Fetch the logged-in customer's profile."""
        # Get or create profile just in case signal didn't fire or row is missing
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        serializer = CustomerProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """Update the logged-in customer's profile details (partial update)."""
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # partial=True ka matlab hai ki client agar sirf address_line_1 bheje, 
        # toh baaki fields null nahi hongi, purani values safe rahengi.
        serializer = CustomerProfileSerializer(profile, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Profile updated successfully!",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)