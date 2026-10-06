from rest_framework import serializers
from .models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from django.contrib.auth import authenticate
from .login_rate_limit import (is_login_blocked,record_failed_login,reset_login_attempts,)
from . google_oauth import verify_google_token , is_google_email_verified, get_google_user_info



class CustomrRegistrationSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'password',
            'phone_number'
        ]
        
        extra_kwargs = {
            'password':{'write_only': True}
        }
        
    def validate_password(self, value):
        validate_password(value)
        return value
    
    def validate_email(self, value):
        return value.lower().strip()
    
    def validate_username(self, value):
        return value.strip()
    
    def validate_phone_number(self, value):
        validator = RegexValidator(
            regex=r'^\+[1-9]\d{1,14}$',
            message='Enter a valid phone number in E.164 format.'
        )

        validator(value)

        return value
        
    def create(self, validated_data):
        password = validated_data.pop('password')
        
        user= User.objects.create_user(
            password = password, 
            role = User.CUSTOMER,
            **validated_data
        )
        
        return user


class VendorRegistrationSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'password',
            'phone_number',
        ]
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        return value.lower().strip()

    def validate_username(self, value):
        return value.strip()

    def validate_phone_number(self, value):
        validator = RegexValidator(
            regex=r'^\+[1-9]\d{1,14}$',
            message='Enter a valid phone number in E.164 format.'
        )
        validator(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            role=User.RESTAURENT,
            **validated_data
        )

        return user


class AdminRegistrationSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'password',
            'phone_number',
        ]
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        return value.lower().strip()

    def validate_username(self, value):
        return value.strip()

    def validate_phone_number(self, value):
        validator = RegexValidator(
            regex=r'^\+[1-9]\d{1,14}$',
            message='Enter a valid phone number in E.164 format.'
        )
        validator(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        user.is_admin = True
        user.is_staff = True
        user.is_active = False
        user.is_superadmin = False
        user.save(
            update_fields=[
                'is_admin',
                'is_staff',
                'is_active',
                'is_superadmin',
            ]
        )

        return user
    
    
class VendorListSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'username',
            'email',
            'phone_number',
            'approval_status',
            'date_joined',
        ]
        
        
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    password = serializers.CharField(
        write_only=True
    )
    
    def validate(self, attrs):
        email = attrs.get('email').lower().strip()
        password = attrs.get('password')
        
        if is_login_blocked(email):
            raise serializers.ValidationError(
                "Too many failed login attempts. Please try again later."
            )
        
        user = authenticate(
            username=email,
            password=password
        )
        
        if not user:
            record_failed_login(email)
            raise serializers.ValidationError(
                "Invalid email or password"
            )
            
        reset_login_attempts(email)
        
        attrs['user'] = user
        
        return attrs
    
    
class GoogleLoginSerializer(serializers.Serializer):

    id_token = serializers.CharField(
        write_only=True
    )

    def validate_id_token(self, value):
        idinfo = verify_google_token(value)

        if not idinfo:
            raise serializers.ValidationError(
                "Invalid Google ID token."
            )

        if not is_google_email_verified(idinfo):
            raise serializers.ValidationError(
                "Google email is not verified."
            )

        return value

    def get_google_user(self):
        idinfo = verify_google_token(
            self.validated_data["id_token"]
        )

        return get_google_user_info(idinfo)

    def create_or_get_user(self, google_data):

        google_id = google_data["google_id"]
        email = google_data["email"]

        try:
            user = User.objects.get(
                google_id=google_id
            )

            return user

        except User.DoesNotExist:

            try:
                User.objects.get(
                    email=email
                )

                raise serializers.ValidationError(
                    "An account with this email already exists. "
                    "Please login with your password."
                )

            except User.DoesNotExist:

                user = User.objects.create_user(
                    first_name=google_data["first_name"],
                    last_name=google_data["last_name"],
                    username=email.split("@")[0],
                    email=email,
                    password=None,
                    role=User.CUSTOMER,
                )

                user.google_id = google_id
                user.is_active = True
                user.set_unusable_password()

                user.save(
                    update_fields=[
                        "google_id",
                        "is_active",
                        "password",
                    ]
                )

                return user


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()

    def get_user(self):
        email = self.validated_data["email"]

        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None



class VerifyResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(
        min_length=6,
        max_length=6
    )

    def validate_email(self, value):
        return value.lower().strip()
    

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        min_length=8
    )
    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        validate_password(attrs["new_password"])

        return attrs
    
