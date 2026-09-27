from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from . serializer import CustomrRegistrationSerializer
from .email_verification import (generate_verification_token,store_verification_token,get_user_id_from_token, delete_verification_token, send_verification_email)
from django.shortcuts import get_object_or_404
from .models import User





class RegisterCustomerView(APIView):

    def post(self, request):
        serializer = CustomrRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            token = generate_verification_token()
            
            store_verification_token(
                user.id,
                token
            )
            
            send_verification_email(user, token)
            
            return Response(
                {
                    "message": "Customer registered successfully",
                    "user": {
                        "id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "username": user.username,
                        "email": user.email,
                        "phone_number": user.phone_number,
                    }
                },
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )


class RegisterRestaurantView(APIView):

    def post(self, request):
        return Response(
            {
                "message": "Register Restaurant API working"
            },
            status=status.HTTP_200_OK
        )


class VerifyEmailView(APIView):
    def get(self, request):
        token = request.query_params.get("token")
        
        if not token:
            return Response(
                {"error": "Verification token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_id = get_user_id_from_token(token)
        
        if not user_id:
            return Response(
                {"error": "Invalid or expired verification token."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        user = get_object_or_404(User, id=user_id)
        
        if user.is_active:
            return Response(
                {"message": "Email is already verified."},
                status=status.HTTP_200_OK
            )
        
        user.is_active = True
        user.save(update_fields=["is_active"])
        
        delete_verification_token(token)
        
        return Response(
            {"message": "Email verified successfully."},
            status=status.HTTP_200_OK
        )