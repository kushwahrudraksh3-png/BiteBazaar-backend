from rest_framework import serializers
from django.contrib.gis.geos import Point
from .models import Restaurant, RestaurantTiming, Category, FoodItem


class RestaurantTimingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantTiming
        fields = ["id", "day", "open_time", "close_time", "is_closed"]


class RestaurantSerializer(serializers.ModelSerializer):
    timings = RestaurantTimingSerializer(many=True, read_only=True)
    
    # Incoming request ke liye temporary write-only fields
    latitude = serializers.FloatField(write_only=True, required=False, allow_null=True)
    longitude = serializers.FloatField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Restaurant
        fields = [
            "id",
            "restaurant_name",
            "description",
            "logo",
            "banner_image",
            "fssai_license_number",
            "support_phone",
            "address",
            "is_open",
            "timings",
            "latitude",
            "longitude",
            "location",  # PostGIS PointField database wala
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "location", "created_at", "updated_at"]

    def create(self, validated_data):
        # Request data se lat/lng alag nikaal lo
        lat = validated_data.pop('latitude', None)
        lng = validated_data.pop('longitude', None)

        # Agar lat aur lng diye hain, toh PostGIS Point banao (Longitude pehle aata hai!)
        if lat is not None and lng is not None:
            validated_data['location'] = Point(lng, lat, srid=4326)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        lat = validated_data.pop('latitude', None)
        lng = validated_data.pop('longitude', None)

        # Agar update mein naye lat/lng aaye hain toh location update karo
        if lat is not None and lng is not None:
            instance.location = Point(lng, lat, srid=4326)

        return super().update(instance, validated_data)


# Upar imports mein check kar lena ki Category aur FoodItem imported hain:
# from .models import Restaurant, RestaurantTiming, Category, FoodItem 
# (Tere file ke hisaab se adjust kar lena)

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        # Hum 'restaurant' field frontend se nahi maangenge (security ke liye), 
        # API khud logged-in user se restaurant nikalegi
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class FoodItemSerializer(serializers.ModelSerializer):
    # Frontend ko category ki sirf ID nahi, balki naam bhi chahiye hota hai dikhane ke liye
    category_name = serializers.ReadOnlyField(source='category.name')
    
    class Meta:
        model = FoodItem
        fields = [
            'id', 'category', 'category_name', 'name', 'description', 
            'price', 'is_veg', 'is_available', 'image', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'category_name', 'created_at', 'updated_at']


class RestaurantStatusSerializer(serializers.Serializer):
    is_open = serializers.BooleanField(required=True)