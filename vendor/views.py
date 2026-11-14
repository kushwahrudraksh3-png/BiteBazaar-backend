from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Restaurant
from .serializers import RestaurantSerializer

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