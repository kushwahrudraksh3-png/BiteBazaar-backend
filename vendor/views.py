from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Restaurant, RestaurantTiming, Category, FoodItem
from django.shortcuts import get_object_or_404
from .serializers import RestaurantSerializer, RestaurantTimingSerializer, CategorySerializer, FoodItemSerializer


class RestaurantProfileView(APIView):
    # Allow only authenticated users to access this view
    permission_classes = [permissions.IsAuthenticated]

    # Helper method to retrieve the restaurant profile for the current user
    def get_object(self, user):
        try:
            return Restaurant.objects.get(user=user)
        except Restaurant.DoesNotExist:
            return None

    # 1. GET Request: Fetch the restaurant profile
    def get(self, request):
        restaurant = self.get_object(request.user)
        if not restaurant:
            return Response(
                {"error": "Restaurant profile has not been created yet."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Serialize the Python object to JSON
        serializer = RestaurantSerializer(restaurant)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 2. POST Request: Create a new restaurant profile
    def post(self, request):
        # Check if the profile already exists to prevent duplicates
        restaurant = self.get_object(request.user)
        if restaurant:
            return Response(
                {"error": "Your restaurant profile already exists."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Pass the incoming JSON data to the serializer
        serializer = RestaurantSerializer(data=request.data)
        
        # If the data is valid, attach the requesting user and save
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        # Return validation errors if the data is invalid
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # 3. PATCH Request: Partially update an existing profile
    def patch(self, request):
        restaurant = self.get_object(request.user)
        if not restaurant:
            return Response(
                {"error": "Profile not found for update."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # partial=True allows updating specific fields without requiring the entire object data
        serializer = RestaurantSerializer(restaurant, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


class RestaurantTimingView(APIView):
    # Allow only authenticated users
    permission_classes = [permissions.IsAuthenticated]

    # Helper method to get the restaurant of the logged-in user
    def get_restaurant(self, user):
        try:
            return Restaurant.objects.get(user=user)
        except Restaurant.DoesNotExist:
            return None

    # 1. GET Request: Fetch all 7-day timings for the vendor's restaurant
    def get(self, request):
        restaurant = self.get_restaurant(request.user)
        if not restaurant:
            return Response(
                {"error": "Restaurant profile not found. Please create a profile first."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Fetch all timings associated with this restaurant
        timings = RestaurantTiming.objects.filter(restaurant=restaurant)
        
        # many=True is used because we are serializing a list of objects (multiple days)
        serializer = RestaurantTimingSerializer(timings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # 2. POST Request: Add or update timing for a specific day
    def post(self, request):
        restaurant = self.get_restaurant(request.user)
        if not restaurant:
            return Response(
                {"error": "Restaurant profile not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        day = request.data.get('day')
        if not day:
            return Response(
                {"error": "The 'day' field is required (1-7)."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if timing for this specific day already exists
        existing_timing = RestaurantTiming.objects.filter(restaurant=restaurant, day=day).first()
        
        # If existing_timing is found, it will UPDATE it. If None, it will CREATE a new one.
        serializer = RestaurantTimingSerializer(existing_timing, data=request.data)
        
        if serializer.is_valid():
            # Automatically link the timing to the vendor's restaurant to prevent spoofing
            serializer.save(restaurant=restaurant)
            
            # Send 200 OK if updated, 201 Created if it's a new entry
            response_status = status.HTTP_200_OK if existing_timing else status.HTTP_201_CREATED
            return Response(serializer.data, status=response_status)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # 3. PATCH Request: Kisi specific din ki timing ka partial update (e.g., sirf is_closed change karna)
    def patch(self, request):
        restaurant = self.get_restaurant(request.user)
        if not restaurant:
            return Response(
                {"error": "Restaurant profile not found."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        day = request.data.get('day')
        if not day:
            return Response(
                {"error": "Update karne ke liye 'day' field (1-7) bhejki zaroori hai."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check karo ki us din ki timing already exist karti hai ya nahi
        existing_timing = RestaurantTiming.objects.filter(restaurant=restaurant, day=day).first()
        if not existing_timing:
            return Response(
                {"error": f"Day {day} ki koi timing nahi mili. Pehle POST use karke create karein."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # partial=True lagaya hai taaki agar sirf ek field aaye (jaise is_closed), toh code error na de
        serializer = RestaurantTimingSerializer(existing_timing, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    

# ==========================================
# CATEGORY API VIEWS
# ==========================================

class CategoryListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            restaurant = Restaurant.objects.get(user=request.user)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant profile not found."}, status=status.HTTP_404_NOT_FOUND)
        
        categories = Category.objects.filter(restaurant=restaurant)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        try:
            restaurant = Restaurant.objects.get(user=request.user)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant profile not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(restaurant=restaurant)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        # Yeh function ensure karega ki vendor sirf apni category access kar sake
        return get_object_or_404(Category, pk=pk, restaurant__user=user)

    def get(self, request, pk):
        category = self.get_object(pk, request.user)
        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        # PUT: Full Update (Saare required fields bhejna zaroori hai)
        category = self.get_object(pk, request.user)
        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        # PATCH: Partial Update (Sirf specific fields update karne ke liye)
        category = self.get_object(pk, request.user)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        category = self.get_object(pk, request.user)
        category.delete()
        return Response({"message": "Category deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


# ==========================================
# FOOD ITEM API VIEWS
# ==========================================

class FoodItemListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            restaurant = Restaurant.objects.get(user=request.user)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant profile not found."}, status=status.HTTP_404_NOT_FOUND)
        
        items = FoodItem.objects.filter(restaurant=restaurant)
        serializer = FoodItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        try:
            restaurant = Restaurant.objects.get(user=request.user)
        except Restaurant.DoesNotExist:
            return Response({"error": "Restaurant profile not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = FoodItemSerializer(data=request.data)
        if serializer.is_valid():
            category = serializer.validated_data.get('category')
            # Security Check: Dish sirf usi category mein add ho sakti hai jo is vendor ki ho
            if category.restaurant != restaurant:
                return Response(
                    {"error": "You cannot add food items to another restaurant's category."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer.save(restaurant=restaurant)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FoodItemDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        return get_object_or_404(FoodItem, pk=pk, restaurant__user=user)

    def get(self, request, pk):
        item = self.get_object(pk, request.user)
        serializer = FoodItemSerializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        # PUT: Full Update
        item = self.get_object(pk, request.user)
        serializer = FoodItemSerializer(item, data=request.data)
        
        if serializer.is_valid():
            # Security check agar category update ho rahi ho
            if 'category' in serializer.validated_data:
                new_category = serializer.validated_data['category']
                if new_category.restaurant.user != request.user:
                    return Response(
                        {"error": "Invalid category selection."}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
                    
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        # PATCH: Partial Update (Jaise sirf price ya availability change karni ho)
        item = self.get_object(pk, request.user)
        serializer = FoodItemSerializer(item, data=request.data, partial=True)
        
        if serializer.is_valid():
            if 'category' in serializer.validated_data:
                new_category = serializer.validated_data['category']
                if new_category.restaurant.user != request.user:
                    return Response(
                        {"error": "Invalid category selection."}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
                    
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        item = self.get_object(pk, request.user)
        item.delete()
        return Response({"message": "Food item deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
    
    
    
