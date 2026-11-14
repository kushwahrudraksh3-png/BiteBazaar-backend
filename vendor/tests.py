from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import Restaurant, RestaurantTiming

User = get_user_model()

class VendorAPITests(APITestCase):
    
    def setUp(self):
        # 1. User with a restaurant profile
        self.user = User.objects.create_user(
            first_name='Test',
            last_name='Vendor',
            username='testvendor',
            email='vendor@bb.com', 
            password='123', 
            role=1
        )
        # 2. User without a restaurant profile (for testing 404 errors)
        self.user_no_profile = User.objects.create_user(
            first_name='New',
            last_name='Vendor',
            username='newvendor',
            email='newvendor@bb.com', 
            password='123', 
            role=1
        )
        
        # Authenticate main user by default
        self.client.force_authenticate(user=self.user)
        self.profile_url = reverse('restaurant-profile')
        self.timing_url = reverse('restaurant-timing')

    # ==========================================
    # RESTAURANT PROFILE TESTS
    # ==========================================

    def test_create_restaurant_profile_success(self):
        self.client.force_authenticate(user=self.user_no_profile)
        payload = {"restaurant_name": "Test Kitchen", "fssai_license_number": "FSSAI_001"}
        response = self.client.post(self.profile_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_duplicate_profile_fails(self):
        Restaurant.objects.create(user=self.user, restaurant_name="Kitchen 1", fssai_license_number="F001")
        payload = {"restaurant_name": "Kitchen 2", "fssai_license_number": "F002"}
        response = self.client.post(self.profile_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_profile_invalid_data(self):
        self.client.force_authenticate(user=self.user_no_profile)
        payload = {"restaurant_name": ""} # Invalid: Empty name
        response = self.client.post(self.profile_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_restaurant_profile_success(self):
        Restaurant.objects.create(user=self.user, restaurant_name="My Kitchen", fssai_license_number="F003")
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_restaurant_profile_not_found(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_restaurant_profile_success(self):
        Restaurant.objects.create(user=self.user, restaurant_name="Old Name", fssai_license_number="F004")
        response = self.client.patch(self.profile_url, {"restaurant_name": "New Name"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_restaurant_profile_not_found(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.patch(self.profile_url, {"is_open": True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_patch_restaurant_profile_invalid_data(self):
        Restaurant.objects.create(user=self.user, restaurant_name="My Kitchen", fssai_license_number="F005")
        response = self.client.patch(self.profile_url, {"fssai_license_number": ""}, format='json') # Invalid FSSAI
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_access_denied(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.profile_url).status_code, status.HTTP_401_UNAUTHORIZED)


    # ==========================================
    # RESTAURANT TIMING TESTS
    # ==========================================

    def test_get_timing_success(self):
        r = Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F006")
        RestaurantTiming.objects.create(restaurant=r, day=1, open_time="09:00:00", close_time="22:00:00")
        response = self.client.get(self.timing_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_timing_no_profile(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.get(self.timing_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_timing_create_success(self):
        Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F007")
        payload = {"day": 2, "open_time": "10:00:00", "close_time": "20:00:00", "is_closed": False}
        response = self.client.post(self.timing_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_post_timing_update_success(self):
        r = Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F008")
        RestaurantTiming.objects.create(restaurant=r, day=3, open_time="09:00:00", close_time="22:00:00")
        # Upsert: Overwriting day 3 via POST
        payload = {"day": 3, "open_time": "11:00:00", "close_time": "23:00:00", "is_closed": True}
        response = self.client.post(self.timing_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_timing_no_profile(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.post(self.timing_url, {"day": 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_timing_missing_day(self):
        Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F009")
        response = self.client.post(self.timing_url, {"open_time": "10:00:00"}, format='json') # day is missing
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_timing_invalid_data(self):
        Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F010")
        payload = {"day": 1, "open_time": "invalid_time", "close_time": "20:00:00"}
        response = self.client.post(self.timing_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- NEW PATCH TESTS ---

    def test_patch_timing_success(self):
        r = Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F011")
        RestaurantTiming.objects.create(restaurant=r, day=4, open_time="09:00:00", close_time="22:00:00", is_closed=False)
        # Partially update to closed
        payload = {"day": 4, "is_closed": True}
        response = self.client.patch(self.timing_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_closed'])

    def test_patch_timing_no_profile(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.patch(self.timing_url, {"day": 1, "is_closed": True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_timing_missing_day(self):
        Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F012")
        # Missing 'day' field
        payload = {"is_closed": True}
        response = self.client.patch(self.timing_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_timing_not_found(self):
        Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F013")
        # Trying to update day 5, which hasn't been created yet
        payload = {"day": 5, "is_closed": True}
        response = self.client.patch(self.timing_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_timing_invalid_data(self):
        r = Restaurant.objects.create(user=self.user, restaurant_name="Kitchen", fssai_license_number="F014")
        RestaurantTiming.objects.create(restaurant=r, day=6, open_time="09:00:00", close_time="22:00:00")
        # Invalid time format
        payload = {"day": 6, "open_time": "abcd"}
        response = self.client.patch(self.timing_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        
    # ==========================================
    # MODEL STRING REPRESENTATION TESTS (For 100% Coverage)
    # ==========================================

    def test_model_str_methods(self):
        # Create a dummy restaurant and timing
        restaurant = Restaurant.objects.create(
            user=self.user, 
            restaurant_name="String Kitchen", 
            fssai_license_number="FSSAI_STR_001"
        )
        timing = RestaurantTiming.objects.create(
            restaurant=restaurant, 
            day=1, 
            open_time="09:00:00", 
            close_time="22:00:00"
        )
        
        # Calling str() executes the __str__ method inside models.py
        self.assertTrue(isinstance(str(restaurant), str))
        self.assertTrue(isinstance(str(timing), str))