from rest_framework import serializers
from .models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator

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