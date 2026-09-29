from rest_framework import serializers
from .models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from django.contrib.auth import authenticate
from .login_rate_limit import (is_login_blocked,record_failed_login,reset_login_attempts,)



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