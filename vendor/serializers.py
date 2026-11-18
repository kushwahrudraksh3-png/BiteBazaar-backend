from rest_framework import serializers
from .models import Restaurant, RestaurantTiming


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

class RestaurantStatusSerializer(serializers.Serializer):
    is_open = serializers.BooleanField(required=True)