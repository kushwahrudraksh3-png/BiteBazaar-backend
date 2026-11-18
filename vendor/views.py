from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Restaurant, RestaurantTiming
from .serializers import RestaurantSerializer, RestaurantTimingSerializer, RestaurantStatusSerializer


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
    



class ToggleRestaurantStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        user = request.user
        
        # 1. Verify if user is a restaurant vendor
        # (Assuming your User model has a role field where RESTAURENT is defined)
        if hasattr(user, 'role') and user.role != getattr(user, 'RESTAURENT', 1):
            return Response(
                {"error": "Only registered restaurant vendors can perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 2. Fetch the vendor's restaurant profile safely
        try:
            restaurant = user.restaurant_profile
        except Restaurant.DoesNotExist:
            return Response(
                {"error": "Restaurant profile not found for this vendor account."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 3. Validate and update status
        serializer = RestaurantStatusSerializer(data=request.data)
        if serializer.is_valid():
            restaurant.is_open = serializer.validated_data['is_open']
            restaurant.save()
            
            status_text = "Open (Accepting Orders)" if restaurant.is_open else "Closed"
            return Response(
                {
                    "message": f"Restaurant status updated successfully to {status_text}.",
                    "restaurant_id": restaurant.id,
                    "restaurant_name": restaurant.restaurant_name,
                    "is_open": restaurant.is_open
                },
                status=status.HTTP_200_OK
            )
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)