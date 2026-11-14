from rest_framework import serializers
from .models import Restaurant, RestaurantTiming

class RestaurantTimingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantTiming
        fields = ['id', 'day', 'open_time', 'close_time', 'is_closed']

class RestaurantSerializer(serializers.ModelSerializer):
    # Yeh nested serializer hai. Ek restaurant get karte hi uski saari timings bhi JSON mein aa jayengi
    timings = RestaurantTimingSerializer(many=True, read_only=True)

    class Meta:
        model = Restaurant
        fields = [
            'id', 'restaurant_name', 'description', 
            'logo', 'banner_image', 'fssai_license_number', 
            'support_phone', 'support_email', 'address', 
            'is_open', 'timings', 'created_at', 'updated_at'
        ]
        # 'user' aur 'location' humne abhi fields mein nahi dale hain. 
        # - user hum API view mein background (request.user) se set karenge security ke liye.
        # - location (PointField) ke liye hum aage chalkar GeoJSON serializer add karenge.