from rest_framework import serializers
from .models import Order, SubOrder, OrderItem

class CheckoutSerializer(serializers.Serializer):
    delivery_address = serializers.CharField(required=True)
    payment_method = serializers.CharField(default='COD') # Cash on Delivery or Online
    
    # Optional: Agar GeoDjango coordinates bhej rahe ho toh yahan handle kar sakte hain
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    
    
class OrderItemSerializer(serializers.ModelSerializer):
    food_item_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'food_item', 'food_item_name', 'quantity', 'price']

    def get_food_item_name(self, obj):
        return obj.food_item.name if obj.food_item else "Deleted Item"


class VendorSubOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_email = serializers.EmailField(source='order.customer.email', read_only=True)
    delivery_address = serializers.CharField(source='order.delivery_address', read_only=True)
    payment_method = serializers.CharField(source='order.payment_method', read_only=True)
    payment_status = serializers.CharField(source='order.payment_status', read_only=True)

    class Meta:
        model = SubOrder
        fields = [
            'id',
            'order',
            'customer_email',
            'delivery_address',
            'payment_method',
            'payment_status',
            'status',
            'suborder_total',
            'admin_commission',
            'vendor_payout',
            'items',
            'created_at',
            'updated_at',
        ]
        