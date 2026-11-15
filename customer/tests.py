from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from customer.cart import Cart

# Apne models yahan import kar lena (App ka naam check kar lena ek baar)
from vendor.models import Restaurant, Category, FoodItem 

User = get_user_model()


class CustomerMenuAPITests(APITestCase):
    def setUp(self):
        """
        Menu testing ke liye Dummy Users aur Restaurant setup
        """
        # 1. Users Setup 
        self.customer_user = User.objects.create_user(
            email='customer@test.com',
            password='testpassword123',
            role=1,     
            first_name='Customer',     
            last_name='User',          
            username='customer_user'   
        )

        self.vendor_user = User.objects.create_user(
            email='vendor@test.com',
            password='testpassword123',
            role=2,
            first_name='Vendor',       
            last_name='User',          
            username='vendor_user'     
        )

        # 2. Restaurants Setup 
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,  
            restaurant_name="Bhaiya Ji Ka Dhaba"
        )
        
        # 3. Menu Setup (Category & Food Items)
        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name="Starters",
            description="Best starters in town"
        )

        # Ye item user ko dikhna chahiye (is_available=True)
        self.food_available = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Paneer Tikka",
            description="Spicy and fresh",
            price=250.00,
            is_veg=True,
            is_available=True 
        )

        # Ye item user ko NAHI dikhna chahiye (is_available=False)
        self.food_unavailable = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Mushroom Tikka",
            description="Out of stock",
            price=200.00,
            is_veg=True,
            is_available=False 
        )

    def test_get_approved_restaurants_list(self):
        """
        Test: List API hit karne par sirf wo restaurants aane chahiye jinka is_approved=True ho.
        (Abhi ke model logic ke hisaab se normal restaurant list)
        """
        # Apna URL name yahan daal dena jo urls.py mein hai
        url = reverse('customer-restaurant-list') # Example name
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['restaurant_name'], "Bhaiya Ji Ka Dhaba")

    def test_get_restaurant_menu_with_only_available_items(self):
        """
        Test: Menu API hit karne par 200 OK aana chahiye, aur 
        nested serializers mein sirf available items aane chahiye.
        """
        url = reverse('customer-restaurant-menu', kwargs={'restaurant_id': self.restaurant.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['restaurant_name'], "Bhaiya Ji Ka Dhaba")

        menu = response.data['menu']
        self.assertEqual(len(menu), 1) 
        self.assertEqual(menu[0]['name'], "Starters")

        # Asli Test: Food items sirf 1 aana chahiye (Mushroom hide hona chahiye)
        food_items = menu[0]['food_items']
        self.assertEqual(len(food_items), 1) 
        self.assertEqual(food_items[0]['name'], "Paneer Tikka")

    def test_get_restaurant_menu_not_found(self):
        """
        Test: Agar koi galat/fake Restaurant ID daale jo database mein nahi hai,
        toh API crash hone ki jagah 404 Not Found return karni chahiye.
        """
        url = reverse('customer-restaurant-menu', kwargs={'restaurant_id': 999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CartAPITests(APITestCase):
    def setUp(self):
        """
        Cart testing ke liye dummy data aur Customer Login setup (Redis Cache handle karke)
        """
        # 0. Redis cache ko clear karo taaki purana cart data test ko kharab na kare
        cache.clear()
        
        # 1. Customer User banaya (Role dynamically assign kiya bouncer ke liye)
        self.customer_user = User.objects.create_user(
            email='customer_cart@test.com',
            password='testpassword123',
            role=1, 
            first_name='Customer',
            last_name='User',
            username='customer_cart_user'
        )
        # HACK: Bouncer ko jo 'CUSTOMER' value chahiye, wahi set karke activate kar diya
        self.customer_user.role = self.customer_user.CUSTOMER 
        self.customer_user.is_active = True
        self.customer_user.save()

        # 2. Vendor User banaya
        self.vendor_user = User.objects.create_user(
            email='vendor_cart@test.com',
            password='testpassword123',
            role=2,  
            first_name='Vendor',
            last_name='User',
            username='vendor_cart_user'
        )
        self.vendor_user.is_active = True
        self.vendor_user.save()

        # 3. Restaurant, Category aur Food Item Setup
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Bhaiya Ji Ka Dhaba"
        )
        
        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name="Main Course",
            description="Heavy meals"
        )
        
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Butter Chicken",
            description="Classic",
            price=300.00,
            is_veg=False,
            is_available=True
        )
        
        # Ye naya item setUp mein add kar (self.food ke niche)
        self.food_unavailable = FoodItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Secret Dish",
            description="Not available right now",
            price=500.00,
            is_veg=True,
            is_available=False
        )

        # 4. Test client ko Customer ke roop mein authenticate karwa diya (IsCustomer pass!)
        self.client.force_authenticate(user=self.customer_user)
        
        self.cart_url = reverse('customer-cart')

    def test_add_item_to_cart_success(self):
        """
        Test: Customer POST request bhej kar cart mein valid item add kar sakta hai.
        """
        payload = {
            "food_id": self.food.id,
            "quantity": 2
        }

        response = self.client.post(self.cart_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("added to cart", response.data['message'])
        self.assertEqual(len(response.data['cart_items']), 1)
        # Price validation (300 * 2 = 600)
        self.assertEqual(response.data['total_price'], 600.00)

    def test_get_cart_details(self):
        """
        Test: Customer GET request bhej kar apna cart dekh sakta hai.
        """
        payload = {"food_id": self.food.id, "quantity": 1}
        self.client.post(self.cart_url, payload, format='json')

        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cart_items = response.data['cart_items']
        
        self.assertEqual(len(cart_items), 1) 
        self.assertEqual(response.data['total_price'], 300.00) 
        
        # Redis items ko Hash dictionary format ({"id": {details}}) mein return karta hai
        food_id_str = str(self.food.id)
        self.assertIn(food_id_str, cart_items)
        self.assertEqual(cart_items[food_id_str]['name'], self.food.name)

    def test_add_invalid_food_to_cart(self):
        """
        Test: Agar customer galat food_id daale toh API 404 (ya 400) return karni chahiye.
        """
        payload = {
            "food_id": 999,
            "quantity": 1
        }
        response = self.client.post(self.cart_url, payload, format='json')

        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST])
        
    
    # ==========================================
    # UPDATE CART (PATCH) TESTS
    # ==========================================

    def test_update_cart_quantity_success(self):
        """
        Test: Customer PATCH request bhej kar cart mein quantity update kar sakta hai.
        """
        # 1. Pehle item cart mein daalo (Quantity: 1)
        self.client.post(self.cart_url, {"food_id": self.food.id, "quantity": 1}, format='json')
        
        # 2. Ab quantity update karo (Quantity: 5)
        payload = {"food_id": self.food.id, "quantity": 5}
        response = self.client.patch(self.cart_url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("updated to 5", response.data['message'])
        
        # Price check (300 * 5 = 1500)
        self.assertEqual(response.data['total_price'], 1500.00)
        
        food_id_str = str(self.food.id)
        self.assertEqual(response.data['cart_items'][food_id_str]['quantity'], 5)

    def test_update_cart_missing_fields(self):
        """
        Test: Agar food_id ya quantity na bheje toh 400 aana chahiye.
        """
        # Sirf food_id bheja, quantity nahi
        response = self.client.patch(self.cart_url, {"food_id": self.food.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_update_cart_invalid_quantity(self):
        """
        Test: Agar quantity 0, negative ya string bheje toh 400 aana chahiye.
        """
        # Case 1: Quantity 0
        response1 = self.client.patch(self.cart_url, {"food_id": self.food.id, "quantity": 0}, format='json')
        self.assertEqual(response1.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("greater than 0", response1.data['error'])
        
        # Case 2: Quantity String (ValueError catch karega)
        response2 = self.client.patch(self.cart_url, {"food_id": self.food.id, "quantity": "abc"}, format='json')
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valid number", response2.data['error'])

    # ==========================================
    # REMOVE FROM CART (DELETE) TESTS
    # ==========================================

    def test_remove_item_from_cart_success(self):
        """
        Test: Customer DELETE request bhej kar cart se item hata sakta hai.
        """
        # 1. Pehle item cart mein daalo
        self.client.post(self.cart_url, {"food_id": self.food.id, "quantity": 2}, format='json')
        
        # 2. Ab item ko delete karo
        payload = {"food_id": self.food.id}
        response = self.client.delete(self.cart_url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("removed from cart", response.data['message'])
        
        # Cart khali ho jana chahiye aur price 0
        self.assertEqual(len(response.data['cart_items']), 0)
        self.assertEqual(response.data['total_price'], 0.00)

    def test_remove_item_missing_food_id(self):
        """
        Test: DELETE request mein agar food_id na ho toh error aana chahiye.
        """
        response = self.client.delete(self.cart_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("food_id is required", response.data['error'])
        
        
    
    def test_add_item_missing_food_id(self):
        """
        Test: Agar POST request mein food_id na ho toh 400 aana chahiye (Line 65)
        """
        response = self.client.post(self.cart_url, {"quantity": 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("food_id is required", response.data['error'])

    def test_add_unavailable_item_to_cart(self):
        """
        Test: Agar item is_available=False hai toh cart mein add nahi hona chahiye (Line 72)
        """
        payload = {"food_id": self.food_unavailable.id, "quantity": 1}
        response = self.client.post(self.cart_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("currently unavailable", response.data['error'])
        
    
    def test_cart_clear_method(self):
        """
        Test: Cart class ka clear() method directly test karna (Line 60 in cart.py)
        Order place hone ke baad cart kaise clear hota hai, ye uska direct test hai.
        """
        # 1. Ek dummy request banayi jisme apna customer user hai
        class DummyRequest:
            pass
        request = DummyRequest()
        request.user = self.customer_user

        # 2. Cart class ko initialize kiya
        cart = Cart(request)
        
        # 3. Cart mein ek item daala aur save karwa diya
        cart.add(food_item=self.food, quantity=2)
        
        # 4. YAHAN HIT HOGI LINE 60 - Clear method call kiya
        cart.clear()
        
        # 5. Check kiya ki Redis se cart sach mein delete ho gaya ya nahi
        cart_key = f"cart_{self.customer_user.id}"
        self.assertIsNone(cache.get(cart_key))