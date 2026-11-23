from django.db import models
from vendor.models import Restaurant , FoodItem
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models as gis_models  # GeoDjango for PostGIS

User = get_user_model()

class Order(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('UPI', 'UPI'),
        ('CASH', 'Cash on Delivery'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('COD', 'Cash on Delivery (Pending Collection)'),
        ('FAILED', 'Failed'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('ACCEPTED', 'Accepted'),
        ('PREPARING', 'Preparing'),
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    
    # Financial Breakdown Fields (New)
    item_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)     # Base price of items
    restaurant_gst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # Govt GST on food
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)   # Delivery charge
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)   # BiteBazaar platform fee
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)    # Final Grand Total (Customer pays this)

    # Payment & Gateway Fields (New)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='UPI')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=250, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Delivery location using GeoDjango for PostGIS distance/tracking
    delivery_location = gis_models.PointField(null=True, blank=True, srid=4326)
    delivery_address = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer.email} [{self.status}] ({self.payment_method})"



class SubOrder(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('ACCEPTED', 'Accepted'),
        ('PREPARING', 'Preparing'),
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='sub_orders')
    vendor = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='sub_orders')
    suborder_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING')
    
    # 🌟 Yeh 2 naye fields add karne hain:
    admin_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # BiteBazaar ki earning snapshot
    vendor_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)     # Restaurant ko milne wala paisa snapshot
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SubOrder #{self.id} (Vendor: {self.vendor_id}) - [{self.status}]"
    
    

class OrderItem(models.Model):
    sub_order = models.ForeignKey(SubOrder, on_delete=models.CASCADE, related_name='items')
    food_item = models.ForeignKey(FoodItem, on_delete=models.SET_NULL, null=True, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)  # Price snapshot at the time of order

    def __str__(self):
        item_name = self.food_item.name if self.food_item else "Deleted Item"
        return f"{self.quantity}x {item_name} (SubOrder #{self.sub_order_id})"
    
    


