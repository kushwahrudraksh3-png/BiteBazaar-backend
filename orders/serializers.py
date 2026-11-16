from rest_framework import serializers
from .models import Order, SubOrder, OrderItem

class CheckoutSerializer(serializers.Serializer):
    delivery_address = serializers.CharField(required=True)
    payment_method = serializers.CharField(default='COD') # Cash on Delivery or Online
    
    # Optional: Agar GeoDjango coordinates bhej rahe ho toh yahan handle kar sakte hain
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)