from django.conf import settings
from django.core.cache import cache
from vendor.models import FoodItem
from decimal import Decimal


class Cart:
    def __init__(self, request):
        self.user_id = request.user.id
        self.cart_id = f"cart_{self.user_id}"
        
        cart = cache.get(self.cart_id)
        if not cart:
            cart = {}
        self.cart = cart
        
    def save(self):
        cache.set(self.cart_id, self.cart, timeout=86400)
        
    def add(self, food_item, quantity=1, update_quantity=False):
        food_id = str(food_item.id)
        
        # FIX: restaurant_id bhi store karenge taaki checkout ke waqt vendor split ho sake
        restaurant_id = food_item.restaurant.id if hasattr(food_item, 'restaurant') else food_item.vendor.id
        
        if food_id not in self.cart:
            self.cart[food_id] = {
                'quantity': 0,
                'price': str(food_item.price),
                'name': food_item.name,
                'restaurant_id': restaurant_id  # <--- Added here
            }
        
        if update_quantity:
            self.cart[food_id]['quantity'] = quantity
        else:
            self.cart[food_id]['quantity'] += quantity
            
        self.save()
        
    def remove(self, food_item):
        food_id = str(food_item.id)
        if food_id in self.cart:
            del self.cart[food_id]
            self.save()
            
    def clear(self):
        cache.delete(self.cart_id)
        
    def get_total_price(self):
        return sum(
            Decimal(item['price']) * item['quantity'] 
            for item in self.cart.values()
        )
    
    def get_cart_items(self):
        """
        Redis dictionary ko list of items mein convert karta hai 
        jisme food_item_id bhi included hota hai.
        """
        items = []
        for food_id, item_data in self.cart.items():
            items.append({
                'food_item_id': int(food_id),
                'restaurant_id': item_data['restaurant_id'],
                'quantity': item_data['quantity'],
                'price': Decimal(item_data['price']),
                'name': item_data['name']
            })
        return items