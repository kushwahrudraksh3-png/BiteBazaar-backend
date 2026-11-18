from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import Restaurant, RestaurantTiming, Category, FoodItem
from django.contrib.gis.geos import Point

User = get_user_model()


class VendorAPITests(APITestCase):

    def setUp(self):
        # 1. User with a restaurant profile
        self.user = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="testvendor",
            email="vendor@bb.com",
            password="123",
            role=1,
        )
        # 2. User without a restaurant profile (for testing 404 errors)
        self.user_no_profile = User.objects.create_user(
            first_name="New",
            last_name="Vendor",
            username="newvendor",
            email="newvendor@bb.com",
            password="123",
            role=1,
        )

        # Authenticate main user by default
        self.client.force_authenticate(user=self.user)
        self.profile_url = reverse("restaurant-profile")
        self.timing_url = reverse("restaurant-timing")

    # ==========================================
    # RESTAURANT PROFILE TESTS
    # ==========================================

    def test_create_restaurant_profile_success(self):
        self.client.force_authenticate(user=self.user_no_profile)
        payload = {
            "restaurant_name": "Test Kitchen",
            "fssai_license_number": "FSSAI_001",
        }
        response = self.client.post(self.profile_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_duplicate_profile_fails(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen 1", fssai_license_number="F001"
        )
        payload = {"restaurant_name": "Kitchen 2", "fssai_license_number": "F002"}
        response = self.client.post(self.profile_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_profile_invalid_data(self):
        self.client.force_authenticate(user=self.user_no_profile)
        payload = {"restaurant_name": ""}  # Invalid: Empty name
        response = self.client.post(self.profile_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_restaurant_profile_success(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="My Kitchen", fssai_license_number="F003"
        )
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_restaurant_profile_not_found(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_restaurant_profile_success(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="Old Name", fssai_license_number="F004"
        )
        response = self.client.patch(
            self.profile_url, {"restaurant_name": "New Name"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_restaurant_profile_not_found(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.patch(self.profile_url, {"is_open": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_restaurant_profile_invalid_data(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="My Kitchen", fssai_license_number="F005"
        )
        response = self.client.patch(
            self.profile_url, {"fssai_license_number": ""}, format="json"
        )  # Invalid FSSAI
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_access_denied(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(self.profile_url).status_code, status.HTTP_401_UNAUTHORIZED
    )
        
    
    def test_create_restaurant_with_lat_lng(self):
        """Test creating restaurant with latitude and longitude (Covers line 47)."""
        # Ensure user has no profile yet
        Restaurant.objects.filter(user=self.user).delete()
        
        url = reverse('restaurant-profile')
        data = {
            "restaurant_name": "Geo Kitchen",
            "fssai_license_number": "FSSAI555555555",
            "latitude": 22.7196,
            "longitude": 75.8577
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_patch_restaurant_with_lat_lng(self):
        """Test updating restaurant location with latitude and longitude (Covers line 57)."""
        # Create initial profile
        Restaurant.objects.create(
            user=self.user,
            restaurant_name="Old Kitchen",
            fssai_license_number="FSSAI666666666"
        )
        url = reverse('restaurant-profile')
        data = {
            "latitude": 22.7300,
            "longitude": 75.8700
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ==========================================
    # RESTAURANT TIMING TESTS
    # ==========================================

    def test_get_timing_success(self):
        r = Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F006"
        )
        RestaurantTiming.objects.create(
            restaurant=r, day=1, open_time="09:00:00", close_time="22:00:00"
        )
        response = self.client.get(self.timing_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_timing_no_profile(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.get(self.timing_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_timing_create_success(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F007"
        )
        payload = {
            "day": 2,
            "open_time": "10:00:00",
            "close_time": "20:00:00",
            "is_closed": False,
        }
        response = self.client.post(self.timing_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_post_timing_update_success(self):
        r = Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F008"
        )
        RestaurantTiming.objects.create(
            restaurant=r, day=3, open_time="09:00:00", close_time="22:00:00"
        )
        # Upsert: Overwriting day 3 via POST
        payload = {
            "day": 3,
            "open_time": "11:00:00",
            "close_time": "23:00:00",
            "is_closed": True,
        }
        response = self.client.post(self.timing_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_post_timing_no_profile(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.post(self.timing_url, {"day": 1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_timing_missing_day(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F009"
        )
        response = self.client.post(
            self.timing_url, {"open_time": "10:00:00"}, format="json"
        )  # day is missing
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_timing_invalid_data(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F010"
        )
        payload = {"day": 1, "open_time": "invalid_time", "close_time": "20:00:00"}
        response = self.client.post(self.timing_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- NEW PATCH TESTS ---

    def test_patch_timing_success(self):
        r = Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F011"
        )
        RestaurantTiming.objects.create(
            restaurant=r,
            day=4,
            open_time="09:00:00",
            close_time="22:00:00",
            is_closed=False,
        )
        # Partially update to closed
        payload = {"day": 4, "is_closed": True}
        response = self.client.patch(self.timing_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_closed"])

    def test_patch_timing_no_profile(self):
        self.client.force_authenticate(user=self.user_no_profile)
        response = self.client.patch(
            self.timing_url, {"day": 1, "is_closed": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_timing_missing_day(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F012"
        )
        # Missing 'day' field
        payload = {"is_closed": True}
        response = self.client.patch(self.timing_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_timing_not_found(self):
        Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F013"
        )
        # Trying to update day 5, which hasn't been created yet
        payload = {"day": 5, "is_closed": True}
        response = self.client.patch(self.timing_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_timing_invalid_data(self):
        r = Restaurant.objects.create(
            user=self.user, restaurant_name="Kitchen", fssai_license_number="F014"
        )
        RestaurantTiming.objects.create(
            restaurant=r, day=6, open_time="09:00:00", close_time="22:00:00"
        )
        # Invalid time format
        payload = {"day": 6, "open_time": "abcd"}
        response = self.client.patch(self.timing_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==========================================
    # MODEL STRING REPRESENTATION TESTS (For 100% Coverage)
    # ==========================================

    def test_model_str_methods(self):
        # Create a dummy restaurant and timing
        restaurant = Restaurant.objects.create(
            user=self.user,
            restaurant_name="String Kitchen",
            fssai_license_number="FSSAI_STR_001",
        )
        timing = RestaurantTiming.objects.create(
            restaurant=restaurant, day=1, open_time="09:00:00", close_time="22:00:00"
        )

        # Calling str() executes the __str__ method inside models.py
        self.assertTrue(isinstance(str(restaurant), str))
        self.assertTrue(isinstance(str(timing), str))


class MenuAPITests(APITestCase):
    def setUp(self):
        # 1. Vendor 1 (Apna Main User)
        self.vendor1 = User.objects.create_user(
            first_name="Vendor",
            last_name="One",
            email="v1@example.com",
            username="vendor1",
            password="Password@123",
            role=User.RESTAURENT,
        )
        self.restaurant1 = Restaurant.objects.create(
            user=self.vendor1,
            restaurant_name="Pizza Hut",
            fssai_license_number="FSSAI12345",  # UNIQUE DUMMY DATA DAAL DIYA
        )

        # 2. Vendor 2 (Hacker / Dusra User)
        self.vendor2 = User.objects.create_user(
            first_name="Vendor",
            last_name="Two",
            email="v2@example.com",
            username="vendor2",
            password="Password@123",
            role=User.RESTAURENT,
        )
        self.restaurant2 = Restaurant.objects.create(
            user=self.vendor2,
            restaurant_name="Dominos",
            fssai_license_number="FSSAI67890",  # ALAG UNIQUE DUMMY DATA DAAL DIYA
        )

        # 3. Vendor Without Profile (404 Test karne ke liye)
        self.vendor3_no_profile = User.objects.create_user(
            first_name="Vendor",
            last_name="Three",
            email="v3@example.com",
            username="vendor3",
            password="Password@123",
            role=User.RESTAURENT,
        )

        # URLs
        self.category_list_url = reverse("category-list-create")
        self.food_list_url = reverse("fooditem-list-create")

    # ==========================================
    # 1. CATEGORY TESTS (100% Coverage)
    # ==========================================
    def test_category_list_and_create_success(self):
        self.client.force_authenticate(user=self.vendor1)

        # Create
        data = {"name": "Starters", "description": "Hot starters"}
        response = self.client.post(self.category_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 1)

        # List
        response_get = self.client.get(self.category_list_url)
        self.assertEqual(response_get.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_get.data), 1)

    def test_category_no_profile_errors(self):
        self.client.force_authenticate(user=self.vendor3_no_profile)
        # GET 404
        self.assertEqual(
            self.client.get(self.category_list_url).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        # POST 404
        self.assertEqual(
            self.client.post(self.category_list_url, {"name": "Test"}).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_category_create_invalid_data(self):
        self.client.force_authenticate(user=self.vendor1)
        response = self.client.post(
            self.category_list_url, {}
        )  # Khali data (Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_category_detail_put_patch_delete(self):
        self.client.force_authenticate(user=self.vendor1)
        category = Category.objects.create(restaurant=self.restaurant1, name="Old Name")
        url = reverse("category-detail", args=[category.id])

        # GET Detail
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

        # PUT Update
        put_resp = self.client.put(url, {"name": "New Name Put"})
        self.assertEqual(put_resp.status_code, status.HTTP_200_OK)

        # PUT Invalid Data
        self.assertEqual(
            self.client.put(url, {}).status_code, status.HTTP_400_BAD_REQUEST
        )

        # PATCH Update
        patch_resp = self.client.patch(url, {"description": "Updated Desc"})
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)

        # PATCH Invalid Data (Simulated by passing invalid type to a required field if needed, but empty {} is valid for PATCH. Let's pass blank name)
        self.assertEqual(
            self.client.patch(url, {"name": ""}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # DELETE
        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertEqual(Category.objects.count(), 0)

    # ==========================================
    # 2. FOOD ITEM TESTS (100% Coverage)
    # ==========================================
    def test_fooditem_list_and_create_success(self):
        self.client.force_authenticate(user=self.vendor1)
        category = Category.objects.create(restaurant=self.restaurant1, name="Main")

        data = {"category": category.id, "name": "Paneer Tikka", "price": "250.00"}
        # POST
        response = self.client.post(self.food_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # GET List
        response_get = self.client.get(self.food_list_url)
        self.assertEqual(response_get.status_code, status.HTTP_200_OK)

    def test_fooditem_no_profile_errors(self):
        self.client.force_authenticate(user=self.vendor3_no_profile)
        self.assertEqual(
            self.client.get(self.food_list_url).status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            self.client.post(self.food_list_url, {"name": "Test"}).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_fooditem_create_invalid_and_forbidden(self):
        self.client.force_authenticate(user=self.vendor1)
        v2_category = Category.objects.create(
            restaurant=self.restaurant2, name="V2 Category"
        )

        # Invalid 400
        self.assertEqual(
            self.client.post(self.food_list_url, {}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # Forbidden 403 (Vendor 1 using Vendor 2's category)
        data = {"category": v2_category.id, "name": "Hack", "price": "100"}
        self.assertEqual(
            self.client.post(self.food_list_url, data).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_fooditem_detail_put_patch_delete(self):
        self.client.force_authenticate(user=self.vendor1)
        cat1 = Category.objects.create(restaurant=self.restaurant1, name="C1")
        item = FoodItem.objects.create(
            restaurant=self.restaurant1, category=cat1, name="Item 1", price="100"
        )
        url = reverse("fooditem-detail", args=[item.id])

        # GET Detail
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

        # PUT Valid
        put_data = {"category": cat1.id, "name": "Updated Name", "price": "150"}
        self.assertEqual(self.client.put(url, put_data).status_code, status.HTTP_200_OK)

        # PUT Invalid (Blank name)
        self.assertEqual(
            self.client.put(
                url, {"category": cat1.id, "name": "", "price": "100"}
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        # PATCH Valid
        self.assertEqual(
            self.client.patch(url, {"price": "200"}).status_code, status.HTTP_200_OK
        )

        # DELETE
        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT
        )

    def test_fooditem_update_forbidden_category(self):
        # Testing if vendor tries to change dish category to another vendor's category via PUT/PATCH
        self.client.force_authenticate(user=self.vendor1)
        cat1 = Category.objects.create(restaurant=self.restaurant1, name="C1")
        cat2 = Category.objects.create(
            restaurant=self.restaurant2, name="C2"
        )  # V2's category
        item = FoodItem.objects.create(
            restaurant=self.restaurant1, category=cat1, name="Item 1", price="100"
        )
        url = reverse("fooditem-detail", args=[item.id])

        # PUT Forbidden
        put_data = {"category": cat2.id, "name": "Item 1", "price": "100"}
        self.assertEqual(
            self.client.put(url, put_data).status_code, status.HTTP_403_FORBIDDEN
        )

        # PATCH Forbidden
        self.assertEqual(
            self.client.patch(url, {"category": cat2.id}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_model_str_methods(self):
        # Category aur FoodItem ke __str__ method ka coverage
        cat = Category.objects.create(restaurant=self.restaurant1, name="Soups")
        item = FoodItem.objects.create(
            restaurant=self.restaurant1,
            category=cat,
            name="Tomato Soup",
            price="150.00",
        )

        self.assertTrue(isinstance(str(cat), str))
        self.assertTrue(isinstance(str(item), str))

    def test_fooditem_patch_invalid(self):
        # views.py ki line 318 (Invalid PATCH) ka coverage
        self.client.force_authenticate(user=self.vendor1)
        cat1 = Category.objects.create(restaurant=self.restaurant1, name="C1")
        item = FoodItem.objects.create(
            restaurant=self.restaurant1, category=cat1, name="Item 1", price="100"
        )
        url = reverse("fooditem-detail", args=[item.id])

        # Galat data bhej kar serializer.errors wali line hit karna
        response = self.client.patch(url, {"price": "invalid_string"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RestaurantSearchTestCase(APITestCase):
    def setUp(self):
        # 1. Vendor create karo with all required custom user fields for Search tests
        self.vendor_user = User.objects.create_user(
            username="search_vendor",
            first_name="Search",
            last_name="Vendor",
            email="vendor_search@example.com",
            password="password123",
            role=1,
        )

        # 2. Restaurant create karo with specific location
        restaurant_location = Point(75.8577, 22.7196, srid=4326)
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Nimadi Bhojan",
            description="manpasand swaad aur traditional food",
            fssai_license_number="FSSAI123456789",
            location=restaurant_location,
        )

        # 3. YEH LINE HONA ZAROORI HAI 👇
        self.search_url = "/api/customer/restaurants/search/"  # Apne actual URL path se match kar lena

    def test_search_by_keyword_name(self):
        """Test searching restaurant by name keyword."""
        response = self.client.get(self.search_url, {"search": "Nimadi"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["restaurant_name"], "Nimadi Bhojan"
        )

    def test_search_by_keyword_description(self):
        """Test searching restaurant by description keyword."""
        response = self.client.get(self.search_url, {"search": "swaad"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["restaurant_name"], "Nimadi Bhojan"
        )

    def test_search_within_radius_success(self):
        """Test searching with user coordinates within 5km radius (should return restaurant)."""
        # User is very close to the restaurant (~0.5 km away)
        user_lat = 22.7200
        user_lng = 75.8580

        response = self.client.get(
            self.search_url, {"user_lat": user_lat, "user_lng": user_lng, "radius": 5.0}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_search_outside_radius_empty(self):
        """Test searching with user coordinates outside 5km radius (should return 0 results)."""
        # User is far away (~15+ km away, e.g., Indore railway station / outer area)
        user_lat = 22.6500
        user_lng = user_lng = 75.7500

        response = self.client.get(
            self.search_url, {"user_lat": user_lat, "user_lng": user_lng, "radius": 5.0}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_search_invalid_coordinates(self):
        """Test search with invalid/malformed coordinates returns 400 bad request."""
        response = self.client.get(
            self.search_url, {"user_lat": "invalid_lat", "user_lng": "invalid_lng"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)


class ToggleRestaurantStatusAPITests(APITestCase):
    def setUp(self):
        # 1. Create a vendor user with required first_name and last_name
        self.vendor_user = User.objects.create_user(
            username="testvendor",
            email="vendor@example.com",
            password="password123",
            first_name="Test",
            last_name="Vendor",
            role=User.RESTAURENT if hasattr(User, 'RESTAURENT') else 1
        )
        
        # 2. Create associated Restaurant profile (default is_open=False)
        self.restaurant = Restaurant.objects.create(
            user=self.vendor_user,
            restaurant_name="Nimadi Rasoi",
            fssai_license_number="12345678901234",
            is_open=False
        )

        # 3. Create a non-vendor user (e.g. customer) for permission testing
        self.customer_user = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="password123",
            first_name="Test",
            last_name="Customer",
            role=0  # Customer role
        )

        # 4. For test_toggle_status_restaurant_profile_not_found, create orphan vendor when needed or inside that specific test:
        self.orphan_vendor_data = {
            "username": "orphanvendor",
            "email": "orphan@example.com",
            "password": "password123",
            "first_name": "Orphan",
            "last_name": "Vendor",
            "role": User.RESTAURENT if hasattr(User, 'RESTAURENT') else 1
        }

        self.url = reverse('restaurant-status-toggle')

    def test_toggle_status_success_to_open(self):
        """Test that a vendor can successfully toggle their restaurant status to open."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.patch(self.url, {"is_open": True}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_open'])
        
        # Verify in database
        self.restaurant.refresh_from_db()
        self.assertTrue(self.restaurant.is_open)

    def test_toggle_status_success_to_closed(self):
        """Test that a vendor can successfully toggle their restaurant status to closed."""
        self.restaurant.is_open = True
        self.restaurant.save()

        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.patch(self.url, {"is_open": False}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_open'])
        
        # Verify in database
        self.restaurant.refresh_from_db()
        self.assertFalse(self.restaurant.is_open)

    def test_toggle_status_invalid_payload(self):
        """Test that sending invalid data (non-boolean) returns 400 Bad Request."""
        self.client.force_authenticate(user=self.vendor_user)
        response = self.client.patch(self.url, {"is_open": "not_a_boolean"}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_toggle_status_forbidden_for_non_vendor(self):
        """Test that non-vendor users (like customers) cannot access the toggle API."""
        self.client.force_authenticate(user=self.customer_user)
        response = self.client.patch(self.url, {"is_open": True}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_toggle_status_restaurant_profile_not_found(self):
        """Test handling when a vendor user does not have a restaurant profile created yet."""
        orphan_vendor = User.objects.create_user(**self.orphan_vendor_data)
        self.client.force_authenticate(user=orphan_vendor)
        
        response = self.client.patch(self.url, {"is_open": True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("Restaurant profile not found", response.data['error'])

    def test_unauthenticated_toggle_request(self):
        """Test that unauthenticated requests are blocked."""
        response = self.client.patch(self.url, {"is_open": True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)