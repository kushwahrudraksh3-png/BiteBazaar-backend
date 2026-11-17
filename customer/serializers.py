from rest_framework import serializers
from vendor.models import Restaurant, FoodItem, Category
from accounts.models import UserProfile

class CustomerRestaurantListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ['id', 'restaurant_name']


class CustomerFoodItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = ['id', 'name', 'description', 'price', 'is_veg', 'image', 'is_available']
        
    
class CustomerCategorySerializer(serializers.ModelSerializer):
    # SerializerMethodField ka use hum tab karte hain jab humein kisi field ka data 
    # directly database se nahi, balki kisi custom logic (function) se nikalna ho.
    food_items = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'food_items']

    def get_food_items(self, obj):
        # 'obj' ka matlab hai current Category jiska data process ho raha hai.
        # Customer ko sirf wahi item dikhega jo available (True) hai.
        available_items = FoodItem.objects.filter(category=obj, is_available=True)
        # Upar wala CustomerFoodItemSerializer use karke serialize kar rahe hain
        return CustomerFoodItemSerializer(available_items, many=True).data
    

class CustomerProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'profile_picture', 'address_line_1', 'address_line_2',
            'country', 'state', 'city', 'pincode', 'latitude', 'longitude',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']