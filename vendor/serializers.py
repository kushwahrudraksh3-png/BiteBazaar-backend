from rest_framework import serializers
from .models import Restaurant, RestaurantTiming, Category, FoodItem


class RestaurantTimingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantTiming
        fields = ["id", "day", "open_time", "close_time", "is_closed"]


class RestaurantSerializer(serializers.ModelSerializer):
    timings = RestaurantTimingSerializer(many=True, read_only=True)

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
            "created_at",
            "updated_at",
        ]


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