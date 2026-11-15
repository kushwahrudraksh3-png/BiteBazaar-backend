from django.conf import settings
from django.core.cache import cache
from vendor.models import FoodItem
from decimal import Decimal


class Cart:
    def __init__(self, request):
        # Hum user ki ID se Redis mein cart ki key banayenge (e.g., 'cart_5')
        self.user_id = request.user.id
        self.cart_id = f"cart_{self.user_id}"
        
        # Redis se is user ka purana cart nikalne ki koshish karo
        cart = cache.get(self.cart_id)
        
        if not cart:
            # Agar purana cart nahi hai, toh ek khali dictionary bana do
            cart = {}
            
        self.cart = cart
        
    
    def save(self):
        cache.set(self.cart_id, self.cart, timeout=86400)
        
    
    def add(self, food_item, quantity=1, update_quantity=False):
        food_id = str(food_item.id) # Redis dictionary mein keys humesha string hoti hain
        
        if food_id not in self.cart:
            # Naya item hai, toh uski details dictionary mein add kar do
            self.cart[food_id] = {
                'quantity': 0,
                'price': str(food_item.price),
                'name': food_item.name
            }
        
        if update_quantity:
            # Agar frontend se bola hai "quantity 5 kar do", toh sidha set karo
            self.cart[food_id]['quantity'] = quantity
            
        else:
            # Warna purani quantity mein 1 jod do
            self.cart[food_id]['quantity'] += quantity
            
        self.save()
        
    
    
    def remove(self, food_item):
        food_id = str(food_item.id)
        if food_id in self.cart:
            del self.cart[food_id]
            self.save()
            
    def clear(self):
        """
        Cart khali karo (Order place hone ke baad kaam aayega).
        """
        cache.delete(self.cart_id)
        
    def get_total_price(self):
        """
        Cart ka total bill calculate karo.
        """
        return sum(
            Decimal(item['price']) * item['quantity'] 
            for item in self.cart.values()
        )