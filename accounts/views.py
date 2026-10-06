from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import status
from . serializer import CustomrRegistrationSerializer, VendorRegistrationSerializer,AdminRegistrationSerializer, VendorListSerializer, LoginSerializer,GoogleLoginSerializer, ForgotPasswordSerializer, VerifyResetOTPSerializer,ResetPasswordSerializer 
from .email_verification import (generate_verification_token,store_verification_token,get_user_id_from_token, delete_verification_token, send_verification_email,resend_verification_email, RESEND_VERIFICATION_COOLDOWN,)
from django.shortcuts import get_object_or_404
from .models import User
from django.core.cache import cache
from .permissions import IsSuperAdmin, IsAdminOrSuperAdmin
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .google_oauth import get_google_authorization_url, exchange_google_code, verify_google_token,get_google_user_info
from .password_reset import (generate_reset_otp,store_reset_otp,send_reset_otp_email,)
from .password_reset import (generate_reset_token,store_reset_token,verify_reset_otp,delete_reset_otp,)
from .password_reset import (verify_reset_token,delete_reset_token,delete_reset_otp,)




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
            
            try:
                send_verification_email(user, token)
            except Exception:
                return Response(
                    {"error":"Failed to send verification email"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
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


class RegisterVendorView(APIView):

    def post(self, request):
        serializer = VendorRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            token = generate_verification_token()
            
            store_verification_token(
                user.id,
                token
            )
            
            try:
                send_verification_email(user, token)
            except Exception:
                return Response(
                    {"error":"Failed to send verification email"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response(
                {
                    "message": "Restaurant registered successfully",
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

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
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
        
class ResendVerificationEmailView(APIView):
    
    def post(self,request):
        email = request.data.get("email")
        
        if not email:
            return Response(
                {"error":"Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        email = email.lower().strip()
        
        rate_limit_key = f"resend_verification:{email}"
        
        if cache.get(rate_limit_key):
            return Response(
                {"error": "Please wait 5 minutes before requesting another verification email."},
                 status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error":"User not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if user.is_active:
            return Response(
                {"message":"Email is already verified"},
                status=status.HTTP_200_OK
            )
        
        token = generate_verification_token()
        
        store_verification_token(
            user.id,
            token
        )
        
        try:
            send_verification_email(
                user,
                token
            )
        except Exception:
            return Response(
                {"error":"Failed to send verification email"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        cache.set(
            rate_limit_key,
            True,
            timeout=RESEND_VERIFICATION_COOLDOWN
        )
        return Response(
            {"message": "Verification email sent successfully."},
            status=status.HTTP_200_OK
        )


class CreateAdminView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = AdminRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            token = generate_verification_token()

            store_verification_token(
                user.id,
                token
            )

            try:
                send_verification_email(
                    user,
                    token
                )
            except Exception:
                return Response(
                    {"error": "Failed to send verification email."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(
                {
                    "message": "Admin created successfully. Verification email sent.",
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

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
        

class VendorListView(APIView):

    permission_classes = [IsAdminOrSuperAdmin,IsAuthenticated]

    def get(self, request):

        vendors = User.objects.filter(
            role=User.RESTAURENT,
            approval_status='pending'
        )

        serializer = VendorListSerializer(
            vendors,
            many=True
        )

        return Response(
            {
                "count": vendors.count(),
                "vendors": serializer.data
            },
            status=status.HTTP_200_OK
        )
        


class ApproveVendorView(APIView):

    permission_classes = [IsAdminOrSuperAdmin]

    def patch(self, request, vendor_id):

        try:
            vendor = User.objects.get(
                id=vendor_id,
                role=User.RESTAURENT
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Vendor not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if vendor.approval_status == 'approved':
            return Response(
                {"message": "Vendor is already approved."},
                status=status.HTTP_200_OK
            )

        if vendor.approval_status == 'rejected':
            return Response(
                {"error": "Rejected vendor cannot be approved directly."},
                status=status.HTTP_400_BAD_REQUEST
            )

        vendor.approval_status = 'approved'
        vendor.save(update_fields=['approval_status'])

        return Response(
            {
                "message": "Vendor approved successfully.",
                "vendor": {
                    "id": vendor.id,
                    "email": vendor.email,
                    "approval_status": vendor.approval_status
                }
            },
            status=status.HTTP_200_OK
        )


class RejectVendorView(APIView):

    permission_classes = [IsAdminOrSuperAdmin]

    def patch(self, request, vendor_id):

        try:
            vendor = User.objects.get(
                id=vendor_id,
                role=User.RESTAURENT
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Vendor not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if vendor.approval_status == 'rejected':
            return Response(
                {"message": "Vendor is already rejected."},
                status=status.HTTP_200_OK
            )

        if vendor.approval_status == 'approved':
            return Response(
                {"error": "Approved vendor cannot be rejected directly."},
                status=status.HTTP_400_BAD_REQUEST
            )

        vendor.approval_status = 'rejected'
        vendor.save(update_fields=['approval_status'])

        return Response(
            {
                "message": "Vendor rejected successfully.",
                "vendor": {
                    "id": vendor.id,
                    "email": vendor.email,
                    "approval_status": vendor.approval_status
                }
            },
            status=status.HTTP_200_OK
        )
        
        
class LoginView(APIView):
    
    def post(self, request):
        
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            if not user.is_active:
                return Response(
                    {"error":"Verify your email first"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if user.role == User.RESTAURENT:
                if user.approval_status != 'approved':
                    return Response(
                        {"error":"Your vendor account is not approved yet"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh":str(refresh),
                    "access":str(refresh.access_token),
                },
                status=status.HTTP_200_OK
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
        
        
class LogoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

        except Exception:
            return Response(
                {"error": "Invalid or already blacklisted refresh token."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        return Response(
            {"message": "Logout successful."},
            status=status.HTTP_200_OK
        )


class GoogleAuthorizationView(APIView):

    def get(self, request):

        authorization_url = get_google_authorization_url()

        return Response(
            {
                "authorization_url": authorization_url
            },
            status=status.HTTP_200_OK
        )
        

class GoogleCallbackView(APIView):

    def get(self, request):

        code = request.query_params.get("code")

        if not code:
            return Response(
                {
                    "error": "Authorization code is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        token_data = exchange_google_code(code)
        
        google_id_token = token_data.get("id_token")

        if not google_id_token:
            return Response(
                {
                    "error": "Google ID token was not returned."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        idinfo = verify_google_token(google_id_token)

        if not idinfo:
            return Response(
                {
                    "error": "Invalid Google ID token."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        
        google_data = get_google_user_info(idinfo)

        if not google_data.get("email"):
            return Response(
                {
                    "error": "Google account email was not provided."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = GoogleLoginSerializer()

        try:
            user = serializer.create_or_get_user(
                google_data
            )

        except serializers.ValidationError as exc:
            return Response(
                {
                    "error": exc.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refresh = RefreshToken.for_user(
            user
        )

        return Response(
            {
                "message": "Google login successful.",
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK
        )
        

class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        user = serializer.get_user()

        if user:
            otp = generate_reset_otp()
            store_reset_otp(user.email, otp)

            try:
                send_reset_otp_email(user, otp)
            except Exception:
                return Response(
                    {"error": "Failed to send password reset email."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(
            {
                "message": (
                    "If an account exists with this email, "
                    "a password reset code has been sent."
                )
            },
            status=status.HTTP_200_OK
        )



class VerifyResetOTPView(APIView):
    def post(self, request):
        serializer = VerifyResetOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        if not verify_reset_otp(email, otp):
            return Response(
                {"error": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        reset_token = generate_reset_token()
        store_reset_token(email, reset_token)

        delete_reset_otp(email)

        return Response(
            {
                "message": "OTP verified successfully.",
                "reset_token": reset_token,
            },
            status=status.HTTP_200_OK
        )



class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data["email"]
        reset_token = serializer.validated_data["reset_token"]
        new_password = serializer.validated_data["new_password"]

        if not verify_reset_token(email, reset_token):
            return Response(
                {"error": "Invalid or expired reset token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Unable to reset password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        delete_reset_token(email)
        delete_reset_otp(email)

        return Response(
            {"message": "Password reset successfully."},
            status=status.HTTP_200_OK
        )