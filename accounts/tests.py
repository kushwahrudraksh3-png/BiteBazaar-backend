
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from accounts.google_oauth import verify_google_token
from rest_framework import serializers
from django.core.management import call_command
from io import StringIO


class CustomerRegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse("register")
        self.valid_data = {
            "first_name": "Rudra",
            "last_name": "Kush",
            "username": "rudrakush",
            "email": "rudrakshkushwah92@gmail.com",
            "password": "rudraksh@123",
            "phone_number": "+919876543210",
        }

    def test_customer_registration_success(self):
        response = self.client.post(
            self.url,
            self.valid_data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

    def test_customer_registration_duplicate_email(self):
        self.client.post(
            self.url,
            self.valid_data,
            format="json"
        )

        duplicate_data = self.valid_data.copy()
        duplicate_data["username"] = "anothercustomer"

        response = self.client.post(
            self.url,
            duplicate_data,
            format="json"
        )



        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )


    def test_customer_registration_invalid_email(self):
        invalid_data = self.valid_data.copy()
        invalid_data["email"] = "invalid-email"

        response = self.client.post(
            self.url,
            invalid_data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
    )

    def test_email_verification_activates_user(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="test-token-123"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.url,
                self.valid_data,
                format="json"
            )

            user = get_user_model().objects.get(
                email=self.valid_data["email"]
            )

            self.assertFalse(user.is_active)

            response = self.client.get(
                reverse("verify-email"),
                {"token": "test-token-123"}
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK
            )

            user.refresh_from_db()
            self.assertTrue(user.is_active)


    def test_email_verification_missing_token(self):
        response = self.client.get(
            reverse("verify-email")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            response.data["error"],
            "Verification token is required."
        )


    def test_email_verification_invalid_token(self):
        response = self.client.get(
            reverse("verify-email"),
            {"token": "invalid-token-123"}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            response.data["error"],
            "Invalid or expired verification token."
        )


    def test_email_verification_already_verified_user(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="test-token-123"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.url,
                self.valid_data,
                format="json"
            )

            user = get_user_model().objects.get(
                email=self.valid_data["email"]
            )

            user.is_active = True
            user.save(update_fields=["is_active"])

            response = self.client.get(
                reverse("verify-email"),
                {"token": "test-token-123"}
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK
            )

            self.assertEqual(
                response.data["message"],
                "Email is already verified."
            )

    def test_resend_verification_missing_email(self):
        response = self.client.post(
            reverse("resend-verification"),
            {},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            response.data["error"],
            "Email is required"
        )

    def test_resend_verification_unknown_email(self):
        with patch("accounts.views.cache.get", return_value=None):
            response = self.client.post(
                reverse("resend-verification"),
                {"email": "missing@example.com"},
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            response.data["error"],
            "User not found"
        )

    def test_resend_verification_rate_limited(self):
        with patch("accounts.views.cache.get", return_value=True):
            response = self.client.post(
                reverse("resend-verification"),
                {"email": "rudrakshkushwah92@gmail.com"},
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS
        )

    def test_resend_verification_success(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="initial-token-123"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.url,
                self.valid_data,
                format="json"
            )

        with patch(
            "accounts.views.cache.get",
            return_value=None
        ), patch(
            "accounts.views.generate_verification_token",
            return_value="resend-token-123"
        ), patch(
            "accounts.views.send_verification_email"
        ) as mock_send:

            response = self.client.post(
                reverse("resend-verification"),
                {"email": self.valid_data["email"]},
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["message"],
            "Verification email sent successfully."
        )

        mock_send.assert_called_once()

    def test_resend_verification_already_verified_user(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="initial-token-123"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.url,
                self.valid_data,
                format="json"
            )

        user = get_user_model().objects.get(
            email=self.valid_data["email"]
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        with patch(
            "accounts.views.cache.get",
            return_value=None
        ), patch(
            "accounts.views.send_verification_email"
        ) as mock_send:

            response = self.client.post(
                reverse("resend-verification"),
                {"email": self.valid_data["email"]},
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertEqual(
            response.data["message"],
            "Email is already verified"
        )
        mock_send.assert_not_called()


    def test_resend_verification_email_failure(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="initial-token-123"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.url,
                self.valid_data,
                format="json"
            )

        with patch(
            "accounts.views.cache.get",
            return_value=None
        ), patch(
            "accounts.views.send_verification_email",
            side_effect=Exception("Email service failed")
        ):
            response = self.client.post(
                reverse("resend-verification"),
                {"email": self.valid_data["email"]},
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        self.assertEqual(
            response.data["error"],
            "Failed to send verification email"
        )

    def test_password_validation_accepts_valid_password(self):
        from accounts.serializer import CustomrRegistrationSerializer

        serializer = CustomrRegistrationSerializer()

        result = serializer.validate_password("StrongPass@123")

        self.assertEqual(result, "StrongPass@123")

    def test_password_validation_rejects_weak_password(self):
        from django.core.exceptions import ValidationError
        from accounts.serializer import CustomrRegistrationSerializer

        serializer = CustomrRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_password("123")

    def test_email_validation_normalizes_email(self):
        from accounts.serializer import CustomrRegistrationSerializer

        serializer = CustomrRegistrationSerializer()

        result = serializer.validate_email("  TEST@EXAMPLE.COM  ")

        self.assertEqual(result, "test@example.com")

    def test_username_validation_strips_whitespace(self):
        from accounts.serializer import CustomrRegistrationSerializer

        serializer = CustomrRegistrationSerializer()

        result = serializer.validate_username("  testuser  ")

        self.assertEqual(result, "testuser")

    def test_phone_number_validation_accepts_valid_number(self):
        from accounts.serializer import CustomrRegistrationSerializer

        serializer = CustomrRegistrationSerializer()

        result = serializer.validate_phone_number("+919876543210")

        self.assertEqual(result, "+919876543210")

    def test_phone_number_validation_rejects_invalid_number(self):
        from django.core.exceptions import ValidationError
        from accounts.serializer import CustomrRegistrationSerializer

        serializer = CustomrRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_phone_number("9876543210")

    def test_create_sets_expected_user_flags(self):
        from accounts.serializer import CustomrRegistrationSerializer
        from accounts.models import User

        serializer = CustomrRegistrationSerializer()

        data = {
            "first_name": "Test",
            "last_name": "User",
            "username": "serializeruser",
            "email": "serializeruser@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543210",
        }

        user = serializer.create(data.copy())

        self.assertEqual(user.role, User.CUSTOMER)
        self.assertFalse(user.is_admin)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superadmin)
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password("StrongPass@123"))

    @patch("accounts.views.send_verification_email")
    @patch(
        "accounts.views.generate_verification_token",
        return_value="customer-registration-token",
    )
    def test_customer_registration_email_failure(
        self,
        mock_generate_token,
        mock_send_email,
    ):
        mock_send_email.side_effect = Exception("Email service failed")

        response = self.client.post(
            self.url,
            self.valid_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        self.assertEqual(
            response.data["error"],
            "Failed to send verification email",
        )

class LoginTests(APITestCase):
    def setUp(self):
        self.register_url = reverse("register")
        self.login_url = reverse("login")

        self.valid_data = {
            "first_name": "Rudra",
            "last_name": "Kush",
            "username": "rudrakush",
            "email": "rudrakshkushwah92@gmail.com",
            "password": "rudraksh@123",
            "phone_number": "+919876543210",
        }

    def test_login_success_returns_jwt_tokens(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="login-test-token"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.register_url,
                self.valid_data,
                format="json"
            )

        user = get_user_model().objects.get(
            email=self.valid_data["email"]
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        response = self.client.post(
            self.login_url,
            {
                "email": self.valid_data["email"],
                "password": self.valid_data["password"],
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="login-test-token"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.register_url,
                self.valid_data,
                format="json"
            )

        user = get_user_model().objects.get(
            email=self.valid_data["email"]
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False
        ), patch(
            "accounts.serializer.record_failed_login"
        ) as mock_failed:

            response = self.client.post(
                self.login_url,
                {
                    "email": self.valid_data["email"],
                    "password": "WrongPass@123",
                },
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            str(response.data["non_field_errors"][0]),
            "Invalid email or password"
        )

        mock_failed.assert_called_once()

    def test_login_unknown_email(self):
        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False
        ), patch(
            "accounts.serializer.record_failed_login"
        ) as mock_failed:

            response = self.client.post(
                self.login_url,
                {
                    "email": "unknown@example.com",
                    "password": "StrongPass@123",
                },
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            str(response.data["non_field_errors"][0]),
            "Invalid email or password"
        )

        mock_failed.assert_called_once()

    def test_login_missing_password(self):
        response = self.client.post(
            self.login_url,
            {"email": "login-test@example.com"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("password", response.data)

    def test_login_missing_email(self):
        response = self.client.post(
            self.login_url,
            {"password": "StrongPass@123"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("email", response.data)

    def test_login_invalid_email_format(self):
        response = self.client.post(
            self.login_url,
            {
                "email": "invalid-email",
                "password": "StrongPass@123",
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("email", response.data)

    def test_login_unverified_user(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="login-test-token"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.register_url,
                self.valid_data,
                format="json"
            )

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False
        ), patch(
            "accounts.serializer.record_failed_login"
        ):
            response = self.client.post(
                self.login_url,
                {
                    "email": self.valid_data["email"],
                    "password": self.valid_data["password"],
                },
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertEqual(
            response.data["error"],
            "Verify your email first"
        )

    def test_login_unapproved_vendor(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "pendingvendor",
            "email": "pending-vendor@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543211",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-test-token"
        ), patch("accounts.views.send_verification_email"):

            registration_response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(
            registration_response.status_code,
            status.HTTP_201_CREATED
        )

        vendor = get_user_model().objects.get(
            email=vendor_data["email"]
        )

        vendor.is_active = True
        vendor.approval_status = "pending"
        vendor.save(update_fields=["is_active", "approval_status"])

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False
        ), patch("accounts.serializer.record_failed_login"):

            response = self.client.post(
                self.login_url,
                {
                    "email": vendor_data["email"],
                    "password": vendor_data["password"],
                },
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertEqual(
            response.data["error"],
            "Your vendor account is not approved yet"
        )

    def test_successful_login_resets_failed_attempts(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="login-test-token"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.register_url,
                self.valid_data,
                format="json"
            )

        user = get_user_model().objects.get(
            email=self.valid_data["email"]
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False
        ), patch(
            "accounts.serializer.reset_login_attempts"
        ) as mock_reset:

            response = self.client.post(
                self.login_url,
                {
                    "email": self.valid_data["email"],
                    "password": self.valid_data["password"],
                },
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        mock_reset.assert_called_once_with(
            self.valid_data["email"]
        )

    def test_refresh_token_returns_access_token(self):
        with patch(
            "accounts.views.generate_verification_token",
            return_value="login-test-token"
        ), patch("accounts.views.send_verification_email"):

            self.client.post(
                self.register_url,
                self.valid_data,
                format="json"
            )

        user = get_user_model().objects.get(
            email=self.valid_data["email"]
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False
        ), patch("accounts.serializer.reset_login_attempts"):

            login_response = self.client.post(
                self.login_url,
                {
                    "email": self.valid_data["email"],
                    "password": self.valid_data["password"],
                },
                format="json"
            )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK
        )

        refresh_token = login_response.data["refresh"]

        response = self.client.post(
            reverse("token-refresh"),
            {"refresh": refresh_token},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )
        self.assertIn("access", response.data)

    def test_refresh_token_invalid(self):
        response = self.client.post(
            reverse("token-refresh"),
            {"refresh": "invalid-refresh-token"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

        self.assertIn("detail", response.data)

    def test_login_approved_vendor_after_admin_approval(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "approvedvendor",
            "email": "approved-vendor@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543212",
        }

        # Register vendor
        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-test-token"
        ), patch("accounts.views.send_verification_email"):

            registration_response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(
            registration_response.status_code,
            status.HTTP_201_CREATED
        )

        vendor = get_user_model().objects.get(
            email=vendor_data["email"]
        )

        # Simulate completed email verification
        vendor.is_active = True
        vendor.save(update_fields=["is_active"])

        # Create an admin for this test
        User = get_user_model()
        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="testadmin",
            email="test-admin@example.com",
            password="AdminPass@123",
            phone_number="+919876543213",
            role=User.CUSTOMER,
        )

        admin.is_active = True
        admin.is_admin = True
        admin.save(update_fields=["is_active", "is_admin"])

        # Admin calls the actual approval API
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin)

        approval_response = admin_client.patch(
            reverse("approve-vendor", args=[vendor.id]),
            {},
            format="json"
        )

        self.assertEqual(
            approval_response.status_code,
            status.HTTP_200_OK
        )

        vendor.refresh_from_db()
        self.assertEqual(vendor.approval_status, "approved")

        # Now the vendor attempts to log in
        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False
        ), patch("accounts.serializer.reset_login_attempts"):

            login_response = self.client.post(
                self.login_url,
                {
                    "email": vendor_data["email"],
                    "password": vendor_data["password"],
                },
                format="json"
            )

        self.assertEqual(
            login_response.status_code,
            status.HTTP_200_OK
        )
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)



class VendorRegistrationTests(APITestCase):

    def test_vendor_registration_success(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "newvendor",
            "email": "new-vendor@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543214",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):

            response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        User = get_user_model()
        vendor = User.objects.get(
            email=vendor_data["email"]
        )

        self.assertEqual(
            vendor.role,
            User.RESTAURENT
        )

        self.assertFalse(vendor.is_active)

    def test_vendor_registration_duplicate_email(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "vendorone",
            "email": "duplicate-vendor@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543214",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):

            first_response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

            self.assertEqual(
                first_response.status_code,
                status.HTTP_201_CREATED
            )

            duplicate_data = vendor_data.copy()
            duplicate_data["username"] = "vendortwo"

            response = self.client.post(
                reverse("register-restaurant"),
                duplicate_data,
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("email", response.data)

    def test_vendor_registration_invalid_email(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "invalidvendor",
            "email": "invalid-email",
            "password": "StrongPass@123",
            "phone_number": "+919876543215",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):

            response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("email", response.data)

    def test_vendor_registration_invalid_phone_number(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "invalidphonevendor",
            "email": "invalid-phone@example.com",
            "password": "StrongPass@123",
            "phone_number": "9876543210",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):

            response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("phone_number", response.data)

    def test_vendor_registration_email_sending_failure(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "emailfailvendor",
            "email": "email-fail@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543216",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch(
            "accounts.views.send_verification_email",
            side_effect=Exception("Email service unavailable")
        ):
            response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        self.assertEqual(
            response.data["error"],
            "Failed to send verification email"
        )

    def test_vendor_registration_weak_password(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "weakpassvendor",
            "email": "weak-pass@example.com",
            "password": "123",
            "phone_number": "+919876543217",
        }

        response = self.client.post(
            reverse("register-restaurant"),
            vendor_data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("password", response.data)


    def test_vendor_registration_missing_required_field(self):
        vendor_data = {
            # "first_name" intentionally missing
            "last_name": "Vendor",
            "username": "missingfieldvendor",
            "email": "missing-field@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543216",
        }

        response = self.client.post(
            reverse("register-restaurant"),
            vendor_data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("first_name", response.data)

    def test_vendor_registration_duplicate_username(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "duplicatevendor",
            "email": "first-vendor@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543218",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):

            first_response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

            vendor_data["email"] = "second-vendor@example.com"

            second_response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED
        )
        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("username", second_response.data)


    def test_vendor_registration_duplicate_email_case_insensitive(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "casevendor1",
            "email": "case-vendor@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543219",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):

            first_response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

            vendor_data["username"] = "casevendor2"
            vendor_data["email"] = "CASE-VENDOR@example.com"

            second_response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", second_response.data)

    def test_vendor_registration_missing_password(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "missingpasswordvendor",
            "email": "missing-password@example.com",
            "phone_number": "+919876543220",
        }

        response = self.client.post(
            reverse("register-restaurant"),
            vendor_data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )
        self.assertIn("password", response.data)

    def test_vendor_registration_status_is_pending(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "pendingstatusvendor",
            "email": "pending-status@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543221",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):
            response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        vendor = get_user_model().objects.get(
            email="pending-status@example.com"
        )
        self.assertEqual(vendor.approval_status, "pending")


    def test_vendor_registration_user_is_inactive(self):
        vendor_data = {
            "first_name": "Test",
            "last_name": "Vendor",
            "username": "inactivevendor",
            "email": "inactive-vendor@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543222",
        }

        with patch(
            "accounts.views.generate_verification_token",
            return_value="vendor-registration-token"
        ), patch("accounts.views.send_verification_email"):
            response = self.client.post(
                reverse("register-restaurant"),
                vendor_data,
                format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        vendor = get_user_model().objects.get(
            email="inactive-vendor@example.com"
        )
        self.assertFalse(vendor.is_active)


    def test_rejected_vendor_cannot_login(self):
        User = get_user_model()
        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="rejectedvendor",
            email="rejected-vendor@example.com",
            password="StrongPass@123",
            role=User.RESTAURENT,
        )
        vendor.is_active = True
        vendor.approval_status = "rejected"
        vendor.save()

        response = self.client.post(
            reverse("login"),
            {
                "email": "rejected-vendor@example.com",
                "password": "StrongPass@123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertIn("error", response.data)


    def test_non_admin_cannot_approve_vendor(self):
        User = get_user_model()

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="testvendor_approve",
            email="testvendor_approve@example.com",
            password="StrongPass@123",
            role=User.RESTAURENT,
        )

        customer = User.objects.create_user(
            first_name="Test",
            last_name="Customer",
            username="testcustomer_approve",
            email="testcustomer_approve@example.com",
            password="StrongPass@123",
            role=User.CUSTOMER,
        )

        self.client.force_authenticate(user=customer)

        response = self.client.patch(
            reverse("approve-vendor", kwargs={"vendor_id": vendor.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        vendor.refresh_from_db()
        self.assertEqual(vendor.approval_status, "pending")

    def test_unauthenticated_user_cannot_approve_vendor(self):
        User = get_user_model()

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="testvendor_unauth",
            email="testvendor_unauth@example.com",
            password="StrongPass@123",
            role=User.RESTAURENT,
        )

        response = self.client.patch(
            reverse("approve-vendor", kwargs={"vendor_id": vendor.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        vendor.refresh_from_db()
        self.assertEqual(vendor.approval_status, "pending")

    def test_admin_can_reject_vendor(self):
        User = get_user_model()

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="testvendor_reject",
            email="testvendor_reject@example.com",
            password="StrongPass@123",
            role=User.RESTAURENT,
        )

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="testadmin_reject",
            email="testadmin_reject@example.com",
            password="StrongPass@123",
            role=User.CUSTOMER,
        )

        admin.is_staff = True
        admin.is_admin = True
        admin.is_active = True
        admin.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("approve-vendor", kwargs={"vendor_id": vendor.id}),
            {"approval_status": "rejected"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_approve_vendor(self):
        User = get_user_model()

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="testvendor_approve2",
            email="testvendor_approve2@example.com",
            password="StrongPass@123",
            role=User.RESTAURENT,
        )

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="testadmin_approve2",
            email="testadmin_approve2@example.com",
            password="StrongPass@123",
            role=User.CUSTOMER,
        )

        admin.is_admin = True
        admin.is_active = True
        admin.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("approve-vendor", kwargs={"vendor_id": vendor.id}),
            {"approval_status": "approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        vendor.refresh_from_db()
        self.assertEqual(vendor.approval_status, "approved")

    def test_vendor_email_validation_rejects_duplicate_email(self):
        from django.contrib.auth import get_user_model
        from rest_framework.exceptions import ValidationError
        from accounts.serializer import VendorRegistrationSerializer

        User = get_user_model()

        User.objects.create_user(
            first_name="Existing",
            last_name="User",
            username="existinguser",
            email="vendor@example.com",
            password="StrongPass@123",
        )

        serializer = VendorRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_email(" VENDOR@EXAMPLE.COM ")

    def test_reject_vendor_not_found(self):
        User = get_user_model()

        admin = User.objects.create_user(
        first_name="Test",
        last_name="Admin",
        username="reject_admin_404",
        email="reject_admin_404@example.com",
        password="StrongPass@123",
        )

        admin.is_staff = True
        admin.is_admin = True
        admin.is_active = True
        admin.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("reject-vendor", kwargs={"vendor_id": 999999}),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(response.data["error"], "Vendor not found.")

    def test_reject_already_rejected_vendor(self):
        User = get_user_model()

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="reject_admin_existing",
            email="reject_admin_existing@example.com",
            password="StrongPass@123",
        )
        admin.is_staff = True
        admin.is_admin = True
        admin.is_active = True
        admin.save()

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="rejected_vendor",
            email="rejected_vendor@example.com",
            password="StrongPass@123",
        )
        vendor.role = User.RESTAURENT
        vendor.approval_status = "rejected"
        vendor.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("reject-vendor", kwargs={"vendor_id": vendor.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Vendor is already rejected.",
        )

    def test_reject_approved_vendor_returns_400(self):
        User = get_user_model()

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="reject_admin_approved",
            email="reject_admin_approved@example.com",
            password="StrongPass@123",
        )
        admin.is_staff = True
        admin.is_admin = True
        admin.is_active = True
        admin.save()

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="approved_vendor",
            email="approved_vendor@example.com",
            password="StrongPass@123",
        )
        vendor.role = User.RESTAURENT
        vendor.approval_status = "approved"
        vendor.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("reject-vendor", kwargs={"vendor_id": vendor.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Approved vendor cannot be rejected directly.",
        )

    def test_reject_pending_vendor_successfully(self):
        User = get_user_model()

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="reject_admin_success",
            email="reject_admin_success@example.com",
            password="StrongPass@123",
        )
        admin.is_staff = True
        admin.is_admin = True
        admin.is_active = True
        admin.save()

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="pending_vendor",
            email="pending_vendor@example.com",
            password="StrongPass@123",
        )
        vendor.role = User.RESTAURENT
        vendor.approval_status = "pending"
        vendor.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("reject-vendor", kwargs={"vendor_id": vendor.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Vendor rejected successfully.",
        )

        vendor.refresh_from_db()
        self.assertEqual(vendor.approval_status, "rejected")



class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            first_name="Test",
            last_name="User",
            username="passwordresetuser",
            email="reset@example.com",
            password="OldPassword@123",
            role=get_user_model().CUSTOMER,
        )

        self.user.is_active = True
        self.user.save(update_fields=["is_active"])

        self.forgot_url = reverse("forgot-password")
        self.verify_otp_url = reverse("verify-reset-otp")
        self.reset_url = reverse("reset-password")

    @patch("accounts.views.send_reset_otp_email")
    def test_forgot_password_success(self, mock_send_email):
        response = self.client.post(
            self.forgot_url,
            {"email": self.user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_email.assert_called_once()

    def test_forgot_password_unknown_email(self):
        response = self.client.post(
            self.forgot_url,
            {"email": "unknown@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)

    def test_forgot_password_invalid_email(self):
        response = self.client.post(
            self.forgot_url,
            {"email": "invalid-email"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch("accounts.views.send_reset_otp_email")
    def test_forgot_password_email_failure(self, mock_send_email):
        mock_send_email.side_effect = Exception("Email service failed")

        response = self.client.post(
            self.forgot_url,
            {"email": self.user.email},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        self.assertEqual(
            response.data["error"],
            "Failed to send password reset email.",
        )

    @patch("accounts.views.verify_reset_otp", return_value=True)
    @patch("accounts.views.generate_reset_token", return_value="test-reset-token")
    @patch("accounts.views.store_reset_token")
    @patch("accounts.views.delete_reset_otp")
    def test_verify_reset_otp_success(
        self,
        mock_delete_otp,
        mock_store_token,
        mock_generate_token,
        mock_verify_otp,
    ):
        response = self.client.post(
            self.verify_otp_url,
            {
                "email": self.user.email,
                "otp": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["reset_token"],
            "test-reset-token",
        )
        mock_store_token.assert_called_once_with(
            self.user.email,
            "test-reset-token",
        )
        mock_delete_otp.assert_called_once_with(self.user.email)

    @patch("accounts.views.verify_reset_otp", return_value=False)
    def test_verify_reset_otp_invalid(self, mock_verify_otp):
        response = self.client.post(
            self.verify_otp_url,
            {
                "email": self.user.email,
                "otp": "123456",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Invalid or expired OTP.",
        )

    def test_verify_reset_otp_invalid_length(self):
        response = self.client.post(
            self.verify_otp_url,
            {
                "email": self.user.email,
                "otp": "123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


    @patch("accounts.views.verify_reset_token", return_value=True)
    @patch("accounts.views.delete_reset_token")
    @patch("accounts.views.delete_reset_otp")
    def test_reset_password_success(
        self,
        mock_delete_otp,
        mock_delete_token,
        mock_verify_token,
    ):
        response = self.client.post(
            self.reset_url,
            {
                "email": self.user.email,
                "reset_token": "valid-reset-token",
                "new_password": "NewStrongPass@456",
                "confirm_password": "NewStrongPass@456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Password reset successfully.",
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass@456"))
        self.assertFalse(self.user.check_password("OldPassword@123"))

        mock_delete_token.assert_called_once_with(self.user.email)
        mock_delete_otp.assert_called_once_with(self.user.email)

    @patch("accounts.views.verify_reset_token", return_value=False)
    def test_reset_password_invalid_token(self, mock_verify_token):
        response = self.client.post(
            self.reset_url,
            {
                "email": self.user.email,
                "reset_token": "invalid-token",
                "new_password": "NewStrongPass@456",
                "confirm_password": "NewStrongPass@456",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Invalid or expired reset token.",
        )

    def test_reset_password_mismatched_passwords(self):
        response = self.client.post(
            self.reset_url,
            {
                "email": self.user.email,
                "reset_token": "valid-reset-token",
                "new_password": "NewStrongPass@456",
                "confirm_password": "DifferentPass@789",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("confirm_password", response.data)

    def test_reset_password_weak_password(self):
        response = self.client.post(
            self.reset_url,
            {
                "email": self.user.email,
                "reset_token": "valid-reset-token",
                "new_password": "12345678",
                "confirm_password": "12345678",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


    @patch("accounts.views.verify_reset_token", return_value=True)
    def test_reset_password_user_not_found(self, mock_verify_token):
        response = self.client.post(
            self.reset_url,
            {
                "email": "missing@example.com",
                "reset_token": "valid-reset-token",
                "new_password": "NewStrongPass@456",
                "confirm_password": "NewStrongPass@456",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Unable to reset password.",
        )



class PasswordResetCacheTests(APITestCase):

    def setUp(self):
        self.email = "cache-test@example.com"
        cache.delete(f"password_reset_token:{self.email}")

    def test_reset_token_is_stored_in_cache(self):
        from accounts.password_reset import (
            store_reset_token,
            get_reset_token,
        )

        email = self.email
        token = "test-reset-token"

        store_reset_token(email, token)

        self.assertEqual(
            get_reset_token(email),
            token,
        )

    def test_reset_token_is_deleted_from_cache(self):
        from accounts.password_reset import (
            store_reset_token,
            get_reset_token,
            delete_reset_token,
        )

        email = self.email
        token = "test-reset-token"

        store_reset_token(email, token)
        delete_reset_token(email)

        self.assertIsNone(get_reset_token(email))



class PasswordResetHelperTests(APITestCase):

    def setUp(self):
        self.email = "helper@example.com"
        cache.delete(f"password_reset_otp:{self.email}")
        cache.delete(f"password_reset_token:{self.email}")

    def test_get_reset_otp_returns_stored_otp(self):
        from accounts.password_reset import store_reset_otp, get_reset_otp

        store_reset_otp(self.email, "123456")

        self.assertEqual(get_reset_otp(self.email), "123456")

    def test_delete_reset_otp_removes_stored_otp(self):
        from accounts.password_reset import (
            store_reset_otp,
            get_reset_otp,
            delete_reset_otp,
        )

        store_reset_otp(self.email, "123456")
        delete_reset_otp(self.email)

        self.assertIsNone(get_reset_otp(self.email))

    def test_verify_reset_otp_returns_false_when_missing(self):
        from accounts.password_reset import verify_reset_otp

        self.assertFalse(verify_reset_otp(self.email, "123456"))


    def test_verify_reset_otp_returns_false_when_incorrect(self):
        from accounts.password_reset import store_reset_otp, verify_reset_otp

        store_reset_otp(self.email, "123456")

        self.assertFalse(verify_reset_otp(self.email, "654321"))


    def test_verify_reset_otp_returns_true_when_correct(self):
        from accounts.password_reset import store_reset_otp, verify_reset_otp

        store_reset_otp(self.email, "123456")

        self.assertTrue(verify_reset_otp(self.email, "123456"))

    def test_get_reset_token_returns_stored_token(self):
        from accounts.password_reset import store_reset_token, get_reset_token

        store_reset_token(self.email, "test-reset-token")

        self.assertEqual(get_reset_token(self.email), "test-reset-token")


    def test_get_reset_token_returns_none_when_missing(self):
        from accounts.password_reset import get_reset_token

        self.assertIsNone(get_reset_token(self.email))

    def test_verify_reset_token_returns_false_when_missing(self):
        from accounts.password_reset import verify_reset_token

        self.assertFalse(
            verify_reset_token(self.email, "test-reset-token")
        )


    def test_verify_reset_token_returns_false_when_incorrect(self):
        from accounts.password_reset import store_reset_token, verify_reset_token

        store_reset_token(self.email, "correct-token")

        self.assertFalse(
            verify_reset_token(self.email, "wrong-token")
        )


    def test_verify_reset_token_returns_true_when_correct(self):
        from accounts.password_reset import store_reset_token, verify_reset_token

        store_reset_token(self.email, "correct-token")

        self.assertTrue(
            verify_reset_token(self.email, "correct-token")
        )

    def test_generate_reset_otp_returns_six_digit_string(self):
        from accounts.password_reset import generate_reset_otp

        otp = generate_reset_otp()

        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    @patch("accounts.password_reset.send_mail")
    def test_send_reset_otp_email_success(self, mock_send_mail):
        from types import SimpleNamespace
        from accounts.password_reset import send_reset_otp_email

        user = SimpleNamespace(email="helper@example.com")

        send_reset_otp_email(user, "123456")

        mock_send_mail.assert_called_once()

        kwargs = mock_send_mail.call_args.kwargs
        self.assertEqual(kwargs["subject"], "BiteBazaar Password Reset OTP")
        self.assertEqual(kwargs["recipient_list"], [user.email])
        self.assertIn("123456", kwargs["message"])

    @patch("accounts.password_reset.send_mail")
    def test_send_reset_otp_email_reraises_bad_header_error(self, mock_send_mail):
        from types import SimpleNamespace
        from django.core.mail import BadHeaderError
        from accounts.password_reset import send_reset_otp_email

        mock_send_mail.side_effect = BadHeaderError("Invalid email header")
        user = SimpleNamespace(email="helper@example.com")

        with self.assertRaises(BadHeaderError):
            send_reset_otp_email(user, "123456")


    @patch("accounts.password_reset.send_mail")
    def test_send_reset_otp_email_reraises_general_exception(self, mock_send_mail):
        from types import SimpleNamespace
        from accounts.password_reset import send_reset_otp_email

        mock_send_mail.side_effect = Exception("Email service failed")
        user = SimpleNamespace(email="helper@example.com")

        with self.assertRaises(Exception):
            send_reset_otp_email(user, "123456")

    def test_generate_reset_token_returns_non_empty_string(self):
        from accounts.password_reset import generate_reset_token

        token = generate_reset_token()

        self.assertIsInstance(token, str)
        self.assertTrue(token)

    @patch("accounts.email_verification.send_mail")
    def test_send_verification_email_success(self, mock_send_mail):
        from types import SimpleNamespace
        from django.conf import settings
        from accounts.email_verification import send_verification_email

        user = SimpleNamespace(email="verify@example.com")
        token = "test-verification-token"

        send_verification_email(user, token)

        mock_send_mail.assert_called_once()

        kwargs = mock_send_mail.call_args.kwargs

        self.assertEqual(
            kwargs["subject"],
            "Verify your BiteBazaar account",
        )
        self.assertEqual(kwargs["recipient_list"], [user.email])
        self.assertIn(token, kwargs["message"])
        self.assertIn(settings.BACKEND_BASE_URL, kwargs["message"])

    @patch("accounts.email_verification.send_mail")
    def test_send_verification_email_bad_header_error(self, mock_send_mail):
        from types import SimpleNamespace
        from django.core.mail import BadHeaderError
        from accounts.email_verification import send_verification_email

        mock_send_mail.side_effect = BadHeaderError("Invalid email header")
        user = SimpleNamespace(email="verify@example.com")

        with self.assertRaises(BadHeaderError):
            send_verification_email(user, "test-verification-token")

    @patch("accounts.email_verification.send_mail")
    def test_send_verification_email_general_exception(self, mock_send_mail):
        from types import SimpleNamespace
        from accounts.email_verification import send_verification_email

        mock_send_mail.side_effect = Exception("Email service failed")
        user = SimpleNamespace(email="verify@example.com")

        with self.assertRaises(Exception):
            send_verification_email(user, "test-verification-token")

    @patch("accounts.email_verification.send_verification_email")
    @patch("accounts.email_verification.store_verification_token")
    @patch(
        "accounts.email_verification.generate_verification_token",
        return_value="new-verification-token",
    )
    def test_resend_verification_email_success(
        self,
        mock_generate_token,
        mock_store_token,
        mock_send_email,
    ):
        from types import SimpleNamespace
        from accounts.email_verification import resend_verification_email

        user = SimpleNamespace(
            id=123,
            email="verify@example.com",
        )

        resend_verification_email(user)

        mock_generate_token.assert_called_once()
        mock_store_token.assert_called_once_with(
            user.id,
            "new-verification-token",
        )
        mock_send_email.assert_called_once_with(
            user,
            "new-verification-token",
        )



class LoginRateLimitHelperTests(APITestCase):

    def setUp(self):
        from django.core.cache import cache
        from accounts.login_rate_limit import get_login_attempt_key

        self.email = "login-limit@example.com"
        self.key = get_login_attempt_key(self.email)
        cache.delete(self.key)

    def test_record_failed_login_increments_attempts(self):
        from django.core.cache import cache
        from accounts.login_rate_limit import record_failed_login

        first_attempt = record_failed_login(self.email)
        second_attempt = record_failed_login(self.email)

        self.assertEqual(first_attempt, 1)
        self.assertEqual(second_attempt, 2)
        self.assertEqual(cache.get(self.key), 2)

    def test_login_not_blocked_before_max_attempts(self):
        from accounts.login_rate_limit import (
            record_failed_login,
            is_login_blocked,
        )

        for _ in range(4):
            record_failed_login(self.email)

        self.assertFalse(is_login_blocked(self.email))


    def test_login_blocked_at_max_attempts(self):
        from accounts.login_rate_limit import (
            record_failed_login,
            is_login_blocked,
            MAX_LOGIN_ATTEMPTS,
        )

        for _ in range(MAX_LOGIN_ATTEMPTS):
            record_failed_login(self.email)

        self.assertTrue(is_login_blocked(self.email))


    def test_reset_login_attempts_clears_counter(self):
        from django.core.cache import cache
        from accounts.login_rate_limit import (
            record_failed_login,
            reset_login_attempts,
        )

        record_failed_login(self.email)
        record_failed_login(self.email)

        reset_login_attempts(self.email)

        self.assertIsNone(cache.get(self.key))



class UserManagerTests(APITestCase):

    def test_create_user_without_email_raises_error(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        with self.assertRaisesMessage(
            ValueError, "User must have email address"
        ):
            User.objects.create_user(
                first_name="Test",
                last_name="User",
                username="testuser",
                email="",
                password="TestPass@123",
            )

    def test_create_user_without_username_raises_error(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        with self.assertRaisesMessage(
            ValueError, "User must have username"
        ):
            User.objects.create_user(
                first_name="Test",
                last_name="User",
                username="",
                email="test@example.com",
                password="TestPass@123",
            )

    def test_create_superuser_sets_admin_flags(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        user = User.objects.create_superuser(
            first_name="Admin",
            last_name="User",
            username="adminuser",
            email="admin@example.com",
            password="AdminPass@123",
        )

        self.assertTrue(user.is_admin)
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superadmin)

    def test_user_str_returns_email(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Test",
            last_name="User",
            username="modeltest",
            email="modeltest@example.com",
            password="TestPass@123",
        )

        self.assertEqual(str(user), "modeltest@example.com")


    def test_has_perm_returns_admin_status(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Test",
            last_name="User",
            username="permtest",
            email="permtest@example.com",
            password="TestPass@123",
        )

        self.assertFalse(user.has_perm("some.permission"))
        user.is_admin = True
        self.assertTrue(user.has_perm("some.permission"))


    def test_has_module_perms_returns_true(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Test",
            last_name="User",
            username="modulepermtest",
            email="modulepermtest@example.com",
            password="TestPass@123",
        )

        self.assertTrue(user.has_module_perms("accounts"))



class UserProfileModelTests(APITestCase):

    def test_user_profile_str_returns_user_email(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile

        User = get_user_model()

        user = User.objects.create_user(
            first_name="Test",
            last_name="User",
            username="profiletest",
            email="profiletest@example.com",
            password="TestPass@123",
        )

        profile = UserProfile.objects.get(user=user)

        self.assertEqual(
            str(profile),
            "profiletest@example.com"
        )


    def test_is_super_admin_denies_inactive_superadmin(self):
        from rest_framework.test import APIRequestFactory
        from accounts.permissions import IsSuperAdmin
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Test",
            last_name="User",
            username="inactiveadmin",
            email="inactiveadmin@example.com",
            password="TestPass@123",
            )
        user.is_superadmin = True
        user.is_active = False
        user.save()

        request = APIRequestFactory().get("/")
        request.user = user

        permission = IsSuperAdmin()
        self.assertFalse(permission.has_permission(request, None))


    def test_is_super_admin_denies_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework.test import APIRequestFactory
        from accounts.permissions import IsSuperAdmin

        request = APIRequestFactory().get("/")
        request.user = AnonymousUser()

        permission = IsSuperAdmin()

        self.assertFalse(permission.has_permission(request, None))

    def test_user_update_creates_missing_profile(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile

        User = get_user_model()

        user = User.objects.create_user(
            first_name="Test",
            last_name="User",
            username="missingprofile",
            email="missingprofile@example.com",
            password="TestPass@123",
        )

        UserProfile.objects.filter(user=user).delete()

        user.first_name = "Updated"
        user.save()

        self.assertTrue(
            UserProfile.objects.filter(user=user).exists()
        )



class RemainingSerializerTests(APITestCase):

    def test_vendor_create_sets_restaurant_role(self):
        from accounts.serializer import VendorRegistrationSerializer
        from accounts.models import User

        serializer = VendorRegistrationSerializer()
        data = {
            "first_name": "Vendor",
            "last_name": "Test",
            "username": "vendor_test_serializer",
            "email": "vendor_serializer@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543210",
        }

        user = serializer.create(data.copy())

        self.assertEqual(user.role, User.RESTAURENT)
        self.assertTrue(user.check_password("StrongPass@123"))

    def test_vendor_email_is_normalized(self):
        from accounts.serializer import VendorRegistrationSerializer

        serializer = VendorRegistrationSerializer()

        self.assertEqual(
            serializer.validate_email("  VENDOR@EXAMPLE.COM "),
            "vendor@example.com",
        )

    def test_vendor_username_is_trimmed(self):
        from accounts.serializer import VendorRegistrationSerializer

        serializer = VendorRegistrationSerializer()

        self.assertEqual(
            serializer.validate_username("  vendoruser  "),
            "vendoruser",
        )

    def test_admin_create_sets_expected_flags(self):
        from accounts.serializer import AdminRegistrationSerializer

        serializer = AdminRegistrationSerializer()
        data = {
            "first_name": "Admin",
            "last_name": "Test",
            "username": "admin_test_serializer",
            "email": "admin_serializer@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543211",
        }

        user = serializer.create(data.copy())

        self.assertTrue(user.is_admin)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_superadmin)
        self.assertTrue(user.check_password("StrongPass@123"))

    def test_admin_email_is_normalized(self):
        from accounts.serializer import AdminRegistrationSerializer

        serializer = AdminRegistrationSerializer()

        self.assertEqual(
            serializer.validate_email("  ADMIN@EXAMPLE.COM "),
            "admin@example.com",
        )

    def test_admin_username_is_trimmed(self):
        from accounts.serializer import AdminRegistrationSerializer

        serializer = AdminRegistrationSerializer()

        self.assertEqual(
            serializer.validate_username("  adminuser  "),
            "adminuser",
        )

    def test_admin_phone_accepts_valid_number(self):
        from accounts.serializer import AdminRegistrationSerializer

        serializer = AdminRegistrationSerializer()

        self.assertEqual(
            serializer.validate_phone_number("+919876543210"),
            "+919876543210",
        )

    def test_admin_phone_rejects_invalid_number(self):
        from django.core.exceptions import ValidationError
        from accounts.serializer import AdminRegistrationSerializer

        serializer = AdminRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_phone_number("9876543210")

    def test_login_rejects_blocked_email(self):
        from unittest.mock import patch
        from rest_framework.exceptions import ValidationError
        from accounts.serializer import LoginSerializer

        serializer = LoginSerializer(data={
            "email": "blocked@example.com",
            "password": "StrongPass@123",
        })

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=True,
        ):
            with self.assertRaises(ValidationError):
                serializer.is_valid(raise_exception=True)

    def test_login_rejects_invalid_credentials(self):
        from unittest.mock import patch
        from rest_framework.exceptions import ValidationError
        from accounts.serializer import LoginSerializer

        serializer = LoginSerializer(data={
            "email": "wrong@example.com",
            "password": "WrongPass@123",
        })

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False,
        ), patch(
            "accounts.serializer.authenticate",
            return_value=None,
        ), patch(
            "accounts.serializer.User.objects.filter",
        ) as mock_filter, patch(
            "accounts.serializer.record_failed_login",
        ):
            mock_filter.return_value.first.return_value = None

            with self.assertRaises(ValidationError):
                serializer.is_valid(raise_exception=True)

    def test_login_accepts_inactive_user_with_correct_password(self):
        from unittest.mock import patch
        from django.contrib.auth import get_user_model
        from accounts.serializer import LoginSerializer

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Inactive",
            last_name="User",
            username="inactive_login_serializer",
            email="inactive_login@example.com",
            password="StrongPass@123",
        )

        serializer = LoginSerializer(data={
            "email": "  INACTIVE_LOGIN@EXAMPLE.COM ",
            "password": "StrongPass@123",
        })

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False,
        ), patch(
            "accounts.serializer.authenticate",
            return_value=None,
        ), patch(
            "accounts.serializer.reset_login_attempts",
        ):
            self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.validated_data["user"], user)

    def test_login_accepts_active_user_and_resets_attempts(self):
        from unittest.mock import patch
        from django.contrib.auth import get_user_model
        from accounts.serializer import LoginSerializer

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Active",
            last_name="User",
            username="active_login_serializer",
            email="active_login@example.com",
            password="StrongPass@123",
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        serializer = LoginSerializer(data={
            "email": "ACTIVE_LOGIN@example.com",
            "password": "StrongPass@123",
        })

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False,
        ), patch(
            "accounts.serializer.authenticate",
            return_value=user,
        ), patch(
            "accounts.serializer.reset_login_attempts",
        ) as mock_reset:
            self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.validated_data["user"], user)
        mock_reset.assert_called_once_with("active_login@example.com")

    def test_forgot_password_normalizes_email(self):
        from accounts.serializer import ForgotPasswordSerializer

        serializer = ForgotPasswordSerializer()

        self.assertEqual(
            serializer.validate_email("  USER@EXAMPLE.COM "),
            "user@example.com",
        )

    def test_forgot_password_get_user_returns_none_if_missing(self):
        from accounts.serializer import ForgotPasswordSerializer

        serializer = ForgotPasswordSerializer(
            data={"email": "missing@example.com"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertIsNone(serializer.get_user())

    def test_forgot_password_get_user_returns_existing_user(self):
        from django.contrib.auth import get_user_model
        from accounts.serializer import ForgotPasswordSerializer

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Reset",
            last_name="User",
            username="forgot_serializer_user",
            email="forgot_serializer@example.com",
            password="StrongPass@123",
        )

        serializer = ForgotPasswordSerializer(
            data={"email": user.email}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.get_user(), user)

    def test_verify_reset_otp_normalizes_email(self):
        from accounts.serializer import VerifyResetOTPSerializer

        serializer = VerifyResetOTPSerializer()

        self.assertEqual(
            serializer.validate_email("  USER@EXAMPLE.COM "),
            "user@example.com",
        )

    def test_reset_password_normalizes_email(self):
        from accounts.serializer import ResetPasswordSerializer

        serializer = ResetPasswordSerializer()

        self.assertEqual(
            serializer.validate_email("  USER@EXAMPLE.COM "),
            "user@example.com",
        )

    def test_reset_password_rejects_mismatched_passwords(self):
        from rest_framework.exceptions import ValidationError
        from accounts.serializer import ResetPasswordSerializer

        serializer = ResetPasswordSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate({
                "email": "user@example.com",
                "reset_token": "token123",
                "new_password": "StrongPass@123",
                "confirm_password": "DifferentPass@123",
            })

    def test_reset_password_accepts_matching_valid_passwords(self):
        from accounts.serializer import ResetPasswordSerializer

        serializer = ResetPasswordSerializer()

        result = serializer.validate({
            "email": "user@example.com",
            "reset_token": "token123",
            "new_password": "StrongPass@123",
            "confirm_password": "StrongPass@123",
        })

        self.assertEqual(
            result["new_password"],
            result["confirm_password"],
        )

    def test_vendor_email_validation_rejects_duplicate_email(self):
        from django.contrib.auth import get_user_model
        from rest_framework.exceptions import ValidationError
        from accounts.serializer import VendorRegistrationSerializer

        User = get_user_model()

        User.objects.create_user(
            first_name="Existing",
            last_name="Vendor",
            username="existing_vendor_duplicate",
            email="vendor@example.com",
            password="StrongPass@123",
        )

        serializer = VendorRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_email(" VENDOR@EXAMPLE.COM ")

    def test_vendor_password_validation_accepts_valid_password(self):
        from accounts.serializer import VendorRegistrationSerializer

        serializer = VendorRegistrationSerializer()
        self.assertEqual(
            serializer.validate_password("StrongPass@123"),
            "StrongPass@123",
        )


    def test_vendor_password_validation_rejects_weak_password(self):
        from django.core.exceptions import ValidationError
        from accounts.serializer import VendorRegistrationSerializer

        serializer = VendorRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_password("123")


    def test_vendor_phone_rejects_invalid_number(self):
        from django.core.exceptions import ValidationError
        from accounts.serializer import VendorRegistrationSerializer

        serializer = VendorRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_phone_number("9876543210")


    def test_admin_password_validation_accepts_valid_password(self):
        from accounts.serializer import AdminRegistrationSerializer

        serializer = AdminRegistrationSerializer()
        self.assertEqual(
            serializer.validate_password("StrongPass@123"),
            "StrongPass@123",
        )


    def test_admin_password_validation_rejects_weak_password(self):
        from django.core.exceptions import ValidationError
        from accounts.serializer import AdminRegistrationSerializer

        serializer = AdminRegistrationSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_password("123")


    def test_admin_create_returns_user(self):
        from accounts.serializer import AdminRegistrationSerializer
        from accounts.models import User

        serializer = AdminRegistrationSerializer()
        data = {
            "first_name": "Admin",
            "last_name": "Test",
            "username": "admin_return_test",
            "email": "admin_return@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543212",
        }

        user = serializer.create(data.copy())

        self.assertIsInstance(user, User)
        self.assertEqual(user.email, "admin_return@example.com")


    def test_vendor_list_serializer_serializes_expected_fields(self):
        from accounts.serializer import VendorListSerializer
        from accounts.models import User

        user = User.objects.create_user(
            first_name="List",
            last_name="Vendor",
            username="vendor_list_test",
            email="vendor_list@example.com",
            password="StrongPass@123",
            phone_number="+919876543213",
            role=User.RESTAURENT,
        )

        data = VendorListSerializer(user).data

        self.assertEqual(data["email"], user.email)
        self.assertEqual(data["username"], user.username)
        self.assertIn("approval_status", data)
        self.assertIn("date_joined", data)


    def test_login_normalizes_email_before_authentication(self):
        from unittest.mock import patch
        from accounts.serializer import LoginSerializer
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Login",
            last_name="Normalize",
            username="login_normalize_test",
            email="login_normalize@example.com",
            password="StrongPass@123",
        )
        user.is_active = True
        user.save(update_fields=["is_active"])

        serializer = LoginSerializer(data={
            "email": " LOGIN_NORMALIZE@EXAMPLE.COM ",
            "password": "StrongPass@123",
        })

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False,
        ), patch(
            "accounts.serializer.authenticate",
            return_value=user,
        ) as mock_authenticate, patch(
            "accounts.serializer.reset_login_attempts",
        ):
            self.assertTrue(serializer.is_valid(), serializer.errors)

        mock_authenticate.assert_called_once_with(
            username="login_normalize@example.com",
            password="StrongPass@123",
        )


    def test_login_records_failed_attempt_for_wrong_password(self):
        from unittest.mock import patch
        from rest_framework.exceptions import ValidationError
        from accounts.serializer import LoginSerializer

        serializer = LoginSerializer(data={
            "email": "wrong_password@example.com",
            "password": "WrongPass@123",
        })

        with patch(
            "accounts.serializer.is_login_blocked",
            return_value=False,
        ), patch(
            "accounts.serializer.authenticate",
            return_value=None,
        ), patch(
            "accounts.serializer.record_failed_login",
        ) as mock_record:
            with self.assertRaises(ValidationError):
                serializer.is_valid(raise_exception=True)

        mock_record.assert_called_once_with("wrong_password@example.com")


    def test_verify_reset_otp_rejects_invalid_email(self):
        from accounts.serializer import VerifyResetOTPSerializer

        serializer = VerifyResetOTPSerializer(data={
            "email": "not-an-email",
            "otp": "123456",
        })

        self.assertFalse(serializer.is_valid())


    def test_reset_password_rejects_invalid_email(self):
        from accounts.serializer import ResetPasswordSerializer

        serializer = ResetPasswordSerializer(data={
            "email": "not-an-email",
            "reset_token": "token123",
            "new_password": "StrongPass@123",
            "confirm_password": "StrongPass@123",
        })

        self.assertFalse(serializer.is_valid())

    def test_create_admin_invalid_data_returns_400(self):
        User = get_user_model()

        superadmin = User.objects.create_superuser(
            first_name="Super",
            last_name="Admin",
            username="superadmin_invalid",
            email="superadmin_invalid@example.com",
            password="StrongPass@123",
        )

        self.client.force_authenticate(user=superadmin)

        response = self.client.post(
            reverse("create-admin"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch("accounts.views.send_verification_email")
    @patch(
        "accounts.views.generate_verification_token",
        return_value="admin-verification-token",
    )
    def test_create_admin_success(
        self,
        mock_generate_token,
        mock_send_email,
    ):
        User = get_user_model()

        superadmin = User.objects.create_superuser(
            first_name="Super",
            last_name="Admin",
            username="superadmin_success",
            email="superadmin_success@example.com",
            password="StrongPass@123",
        )

        self.client.force_authenticate(user=superadmin)

        data = {
            "first_name": "Test",
            "last_name": "Admin",
            "username": "newadmin",
            "email": "newadmin@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543210",
        }

        response = self.client.post(
            reverse("create-admin"),
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            response.data["message"],
            "Admin created successfully. Verification email sent.",
        )

        created_user = User.objects.get(email="newadmin@example.com")
        self.assertTrue(created_user.is_admin)
        self.assertFalse(created_user.is_active)

        mock_generate_token.assert_called_once()
        mock_send_email.assert_called_once()

    @patch(
    "accounts.views.send_verification_email",
    side_effect=Exception("Email service failed"),
    )
    @patch(
        "accounts.views.generate_verification_token",
        return_value="admin-failure-token",
    )
    def test_create_admin_email_failure(
        self,
        mock_generate_token,
        mock_send_email,
    ):
        User = get_user_model()

        superadmin = User.objects.create_superuser(
            first_name="Super",
            last_name="Admin",
            username="superadmin_failure",
            email="superadmin_failure@example.com",
            password="StrongPass@123",
        )

        self.client.force_authenticate(user=superadmin)

        data = {
            "first_name": "Test",
            "last_name": "Admin",
            "username": "admin_email_failure",
            "email": "admin_email_failure@example.com",
            "password": "StrongPass@123",
            "phone_number": "+919876543210",
        }

        response = self.client.post(
            reverse("create-admin"),
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        self.assertEqual(
            response.data["error"],
            "Failed to send verification email.",
        )

        mock_generate_token.assert_called_once()
        mock_send_email.assert_called_once()

    def test_vendor_list_returns_pending_vendors_and_count(self):
        User = get_user_model()

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="vendor_list_admin",
            email="vendor_list_admin@example.com",
            password="StrongPass@123",
        )
        admin.is_admin = True
        admin.is_staff = True
        admin.is_active = True
        admin.save()

        vendor1 = User.objects.create_user(
            first_name="Pending",
            last_name="VendorOne",
            username="pending_vendor_one",
            email="pending_vendor_one@example.com",
            password="StrongPass@123",
        )
        vendor1.role = User.RESTAURENT
        vendor1.approval_status = "pending"
        vendor1.save()

        vendor2 = User.objects.create_user(
            first_name="Pending",
            last_name="VendorTwo",
            username="pending_vendor_two",
            email="pending_vendor_two@example.com",
            password="StrongPass@123",
        )
        vendor2.role = User.RESTAURENT
        vendor2.approval_status = "pending"
        vendor2.save()

        self.client.force_authenticate(user=admin)

        response = self.client.get(reverse("vendor-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["vendors"]), 2)

    def test_vendor_list_returns_empty_list_when_no_pending_vendors(self):
        User = get_user_model()

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="empty_vendor_admin",
            email="empty_vendor_admin@example.com",
            password="StrongPass@123",
        )
        admin.is_admin = True
        admin.is_staff = True
        admin.is_active = True
        admin.save()

        self.client.force_authenticate(user=admin)

        response = self.client.get(reverse("vendor-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["vendors"], [])

    def test_approve_already_approved_vendor(self):
        User = get_user_model()

        admin = User.objects.create_superuser(
            first_name="Super",
            last_name="Admin",
            username="approve_admin_existing",
            email="approve_admin_existing@example.com",
            password="StrongPass@123",
        )

        vendor = User.objects.create_user(
            first_name="Test",
            last_name="Vendor",
            username="already_approved_vendor",
            email="already_approved_vendor@example.com",
            password="StrongPass@123",
            role=User.RESTAURENT,
        )
        vendor.approval_status = "approved"
        vendor.save(update_fields=["approval_status"])

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("approve-vendor", kwargs={"vendor_id": vendor.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "Vendor is already approved.",
        )

    def test_approve_rejected_vendor_returns_400(self):
        admin = get_user_model().objects.create_user(
            username="admin_test",
            first_name="Test",
            last_name="Admin",
            email="admin_test@example.com",
            password="StrongPass123!",
            role=1,
        )
        admin.is_admin = True
        admin.is_staff = True
        admin.is_active = True
        admin.save()

        vendor = get_user_model().objects.create_user(
            username="rejected_vendor",
            first_name="Test",
            last_name="Vendor",
            email="rejected_vendor@example.com",
            password="StrongPass123!",
            role=1,
        )
        vendor.approval_status = "rejected"
        vendor.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("approve-vendor", kwargs={"vendor_id": vendor.id}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Rejected vendor cannot be approved directly.",
        )

    def test_approve_vendor_not_found(self):
        User = get_user_model()

        admin = User.objects.create_user(
            first_name="Test",
            last_name="Admin",
            username="approve_admin_404",
            email="approve_admin_404@example.com",
            password="StrongPass@123",
        )
        admin.is_staff = True
        admin.is_admin = True
        admin.is_active = True
        admin.save()

        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            reverse("approve-vendor", kwargs={"vendor_id": 999999}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "Vendor not found.")

    def test_logout_without_refresh_token(self):
        User = get_user_model()

        user = User.objects.create_user(
            first_name="Test",
            last_name="Customer",
            username="logout_customer",
            email="logout_customer@example.com",
            password="StrongPass@123",
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("logout"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Refresh token is required.",
        )

    def test_logout_with_invalid_refresh_token(self):
        User = get_user_model()

        user = User.objects.create_user(
            first_name="Test",
            last_name="Customer",
            username="logout_invalid_customer",
            email="logout_invalid@example.com",
            password="StrongPass@123",
        )

        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("logout"),
            {"refresh": "invalid-refresh-token"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Invalid or already blacklisted refresh token.",
        )

    def test_logout_with_valid_refresh_token(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        User = get_user_model()

        user = User.objects.create_user(
            first_name="Test",
            last_name="Customer",
            username="logout_valid_customer",
            email="logout_valid@example.com",
            password="StrongPass@123",
        )

        self.client.force_authenticate(user=user)
        refresh_token = str(RefreshToken.for_user(user))

        response = self.client.post(
            reverse("logout"),
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Logout successful.")

    @patch("accounts.google_oauth.id_token.verify_oauth2_token")
    def test_verify_google_token_success(self, mock_verify):
        mock_verify.return_value = {
            "sub": "google-user-123",
            "email": "user@example.com",
        }

        result = verify_google_token("valid-google-token")

        self.assertEqual(result["sub"], "google-user-123")


    @patch("accounts.google_oauth.id_token.verify_oauth2_token")
    def test_verify_google_token_invalid(self, mock_verify):
        mock_verify.side_effect = ValueError("Invalid token")

        result = verify_google_token("invalid-google-token")

        self.assertIsNone(result)

    def test_get_google_user_info_returns_user_details(self):
        from accounts.google_oauth import get_google_user_info

        idinfo = {
            "sub": "google-user-123",
            "email": "user@example.com",
            "given_name": "Rudraksh",
            "family_name": "Kushwah",
        }

        result = get_google_user_info(idinfo)

        self.assertEqual(result["google_id"], "google-user-123")
        self.assertEqual(result["email"], "user@example.com")
        self.assertEqual(result["first_name"], "Rudraksh")
        self.assertEqual(result["last_name"], "Kushwah")

    def test_is_google_email_verified_returns_true(self):
        from accounts.google_oauth import is_google_email_verified

        self.assertTrue(
            is_google_email_verified({"email_verified": True})
        )


    def test_is_google_email_verified_returns_false_when_missing(self):
        from accounts.google_oauth import is_google_email_verified

        self.assertFalse(is_google_email_verified({}))

    def test_get_google_authorization_url_contains_required_parameters(self):
        from urllib.parse import urlparse, parse_qs
        from accounts.google_oauth import get_google_authorization_url

        url = get_google_authorization_url()

        parsed_url = urlparse(url)
        params = parse_qs(parsed_url.query)

        self.assertEqual(
            parsed_url.netloc,
            "accounts.google.com",
        )
        self.assertEqual(
            params["response_type"],
            ["code"],
        )
        self.assertEqual(
            params["scope"],
            ["openid email profile"],
        )
        self.assertIn("client_id", params)
        self.assertIn("redirect_uri", params)

    @patch("accounts.google_oauth.requests.post")
    def test_exchange_google_code_success(self, mock_post):
        from accounts.google_oauth import exchange_google_code

        mock_response = mock_post.return_value
        mock_response.json.return_value = {
            "access_token": "access-123",
            "refresh_token": "refresh-123",
        }

        result = exchange_google_code("authorization-code")

        self.assertEqual(result["access_token"], "access-123")
        mock_response.raise_for_status.assert_called_once()
        mock_post.assert_called_once()

    @patch("accounts.google_oauth.requests.post")
    def test_exchange_google_code_raises_http_error(self, mock_post):
        from accounts.google_oauth import exchange_google_code
        import requests

        mock_post.return_value.raise_for_status.side_effect = (
            requests.HTTPError("Google token exchange failed")
        )

        with self.assertRaises(requests.HTTPError):
            exchange_google_code("authorization-code")

        mock_post.assert_called_once()

    @patch("accounts.serializer.verify_google_token", return_value=None)
    def test_google_login_invalid_id_token(self, mock_verify):
        from accounts.serializer import GoogleLoginSerializer

        serializer = GoogleLoginSerializer(
            data={"id_token": "invalid-token"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("Invalid Google ID token.", str(serializer.errors))
        mock_verify.assert_called_once_with("invalid-token")

    @patch(
    "accounts.serializer.verify_google_token",
    return_value={"email_verified": False},
    )
    def test_google_login_unverified_email(self, mock_verify):
        from accounts.serializer import GoogleLoginSerializer

        serializer = GoogleLoginSerializer(
            data={"id_token": "valid-token"},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn(
            "Google email is not verified.",
            str(serializer.errors),
        )
        mock_verify.assert_called_once_with("valid-token")

    def test_create_or_get_user_returns_existing_google_user(self):
        from accounts.serializer import GoogleLoginSerializer

        User = get_user_model()
        user = User.objects.create_user(
            first_name="Google",
            last_name="User",
            username="google_existing",
            email="google_existing@example.com",
            password="StrongPass@123",
        )

        user.google_id = "google-existing-123"
        user.save(update_fields=["google_id"])

        serializer = GoogleLoginSerializer()

        result = serializer.create_or_get_user({
            "google_id": "google-existing-123",
            "email": "google_existing@example.com",
            "first_name": "Google",
            "last_name": "User",
        })

        self.assertEqual(result.id, user.id)

    def test_create_or_get_user_rejects_existing_email(self):
        from rest_framework.exceptions import ValidationError
        from accounts.serializer import GoogleLoginSerializer

        User = get_user_model()
        User.objects.create_user(
            first_name="Existing",
            last_name="User",
            username="existing_google_email",
            email="existing_google@example.com",
            password="StrongPass@123",
        )

        serializer = GoogleLoginSerializer()

        with self.assertRaises(ValidationError):
            serializer.create_or_get_user({
                "google_id": "different-google-id",
                "email": "existing_google@example.com",
                "first_name": "Google",
                "last_name": "User",
            })

    def test_create_or_get_user_creates_new_google_user(self):
        from accounts.serializer import GoogleLoginSerializer

        serializer = GoogleLoginSerializer()

        result = serializer.create_or_get_user({
            "google_id": "new-google-user-123",
            "email": "new_google_user@example.com",
            "first_name": "New",
            "last_name": "GoogleUser",
        })

        self.assertEqual(result.email, "new_google_user@example.com")
        self.assertEqual(result.google_id, "new-google-user-123")
        self.assertTrue(result.is_active)
        self.assertFalse(result.has_usable_password())

    @patch("accounts.serializer.verify_google_token")
    @patch("accounts.serializer.get_google_user_info")
    @patch("accounts.serializer.is_google_email_verified", return_value=True)
    def test_get_google_user_returns_google_user_info(
        self,
        mock_email_verified,
        mock_get_user_info,
        mock_verify_token,
    ):
        from accounts.serializer import GoogleLoginSerializer

        google_data = {
            "google_id": "google-123",
            "email": "test@gmail.com",
            "first_name": "Test",
            "last_name": "User",
        }

        mock_verify_token.return_value = {"sub": "google-123"}
        mock_get_user_info.return_value = google_data

        serializer = GoogleLoginSerializer(data={"id_token": "valid-token"})

        self.assertTrue(serializer.is_valid(), serializer.errors)

        result = serializer.get_google_user()

        self.assertEqual(result, google_data)
        mock_verify_token.assert_called_with("valid-token")
        mock_get_user_info.assert_called_once_with({"sub": "google-123"})


    def test_create_or_get_user_returns_existing_google_user(self):
        from accounts.serializer import GoogleLoginSerializer
        User = get_user_model()
        user = User.objects.create_user(
            first_name="Existing",
            last_name="User",
            username="existing_google",
            email="existing_google@example.com",
            password="TestPass123!",
        )
        user.google_id = "existing-google-123"
        user.save(update_fields=["google_id"])

        serializer = GoogleLoginSerializer()

        result = serializer.create_or_get_user({
            "google_id": "existing-google-123",
            "email": "existing_google@example.com",
            "first_name": "Existing",
            "last_name": "User",
        })

        self.assertEqual(result.pk, user.pk)
        self.assertEqual(result.google_id, "existing-google-123")

    def test_create_or_get_user_creates_new_google_user(self):
        User = get_user_model()
        from accounts.serializer import GoogleLoginSerializer

        serializer = GoogleLoginSerializer()

        result = serializer.create_or_get_user({
            "google_id": "new-google-user-123",
            "email": "new_google_user@example.com",
            "first_name": "New",
            "last_name": "GoogleUser",
        })

        self.assertEqual(result.email, "new_google_user@example.com")
        self.assertEqual(result.google_id, "new-google-user-123")
        self.assertTrue(result.is_active)
        self.assertFalse(result.has_usable_password())

    @patch(
    "accounts.views.get_google_authorization_url",
    return_value="https://accounts.google.com/test-auth",
    )
    def test_google_authorization_view_returns_url(self, mock_get_url):
        response = self.client.get(reverse("google-authorize"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["authorization_url"],
            "https://accounts.google.com/test-auth",
        )
        mock_get_url.assert_called_once()


    def test_google_callback_returns_400_when_code_missing(self):
        response = self.client.get(reverse("google-callback"))

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Authorization code is required.",
        )

    @patch("accounts.views.exchange_google_code")
    def test_google_callback_returns_400_when_id_token_missing(
        self, mock_exchange_code
    ):
        mock_exchange_code.return_value = {"access_token": "access-123"}

        response = self.client.get(
            reverse("google-callback"),
            {"code": "valid-auth-code"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Google ID token was not returned.",
        )
        mock_exchange_code.assert_called_once_with("valid-auth-code")

    @patch("accounts.views.exchange_google_code")
    @patch("accounts.views.verify_google_token", return_value=None)
    def test_google_callback_returns_400_when_id_token_invalid(
        self, mock_verify_token, mock_exchange_code
    ):
        mock_exchange_code.return_value = {
            "id_token": "invalid-token",
            "access_token": "access-123",
        }

        response = self.client.get(
            reverse("google-callback"),
            {"code": "valid-auth-code"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Invalid Google ID token.",
        )
        mock_verify_token.assert_called_once_with("invalid-token")

    @patch("accounts.views.exchange_google_code")
    @patch(
        "accounts.views.verify_google_token",
        return_value={"sub": "google-123"},
    )
    @patch(
        "accounts.views.get_google_user_info",
        return_value={"google_id": "google-123", "email": None},
    )
    def test_google_callback_returns_400_when_email_missing(
        self, mock_get_user_info, mock_verify_token, mock_exchange_code
    ):
        mock_exchange_code.return_value = {"id_token": "valid-token"}

        response = self.client.get(
            reverse("google-callback"),
            {"code": "valid-auth-code"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            response.data["error"],
            "Google account email was not provided.",
        )
        mock_get_user_info.assert_called_once_with({"sub": "google-123"})

    @patch("accounts.views.exchange_google_code")
    @patch(
        "accounts.views.verify_google_token",
        return_value={"sub": "google-123"},
    )
    @patch(
        "accounts.views.get_google_user_info",
        return_value={
            "google_id": "google-123",
            "email": "existing@example.com",
            "first_name": "Existing",
            "last_name": "User",
        },
    )
    @patch(
        "accounts.views.GoogleLoginSerializer.create_or_get_user",
        side_effect=serializers.ValidationError(
            "An account with this email already exists. Please login with your password."
        ),
    )
    def test_google_callback_returns_400_when_user_creation_fails(
        self,
        mock_create_user,
        mock_get_user_info,
        mock_verify_token,
        mock_exchange_code,
    ):
        mock_exchange_code.return_value = {"id_token": "valid-token"}

        response = self.client.get(
            reverse("google-callback"),
            {"code": "valid-auth-code"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        mock_create_user.assert_called_once()

    @patch("accounts.views.RefreshToken.for_user")
    @patch("accounts.views.GoogleLoginSerializer.create_or_get_user")
    @patch(
        "accounts.views.get_google_user_info",
        return_value={
            "google_id": "google-123",
            "email": "google@example.com",
            "first_name": "Google",
            "last_name": "User",
        },
    )
    @patch("accounts.views.verify_google_token", return_value={"sub": "google-123"})
    @patch("accounts.views.exchange_google_code")
    def test_google_callback_success(
        self,
        mock_exchange_code,
        mock_verify_token,
        mock_get_user_info,
        mock_create_user,
        mock_refresh_for_user,
    ):
        User = get_user_model()
        user = User.objects.create_user(
            first_name="Google",
            last_name="User",
            username="google_user",
            email="google@example.com",
            password="TestPass123!",
        )

        mock_exchange_code.return_value = {"id_token": "valid-token"}
        mock_create_user.return_value = user

        mock_refresh = mock_refresh_for_user.return_value
        mock_refresh.access_token = "fake-access-token"
        mock_refresh.__str__.return_value = "fake-refresh-token"

        response = self.client.get(
            reverse("google-callback"),
            {"code": "valid-auth-code"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Google login successful.")
        self.assertEqual(response.data["refresh"], "fake-refresh-token")
        self.assertEqual(response.data["access"], "fake-access-token")
        mock_create_user.assert_called_once()
        mock_refresh_for_user.assert_called_once_with(user)

class CreateSuperadminCommandTests(APITestCase):

    @patch("builtins.input", side_effect=[
        "admin@example.com",
        "superadmin",
        "Super",
        "Admin",
        "StrongPass@123",
        "+919876543210",
    ])
    def test_create_superadmin_command(self, mock_input):
        User = get_user_model()
        output = StringIO()

        call_command("create_superadmin", stdout=output)

        user = User.objects.get(email="admin@example.com")

        self.assertTrue(user.is_admin)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superadmin)
        self.assertTrue(user.is_active)
        self.assertIn(
            "Super Admin created successfully.",
            output.getvalue(),
        )
        self.assertEqual(mock_input.call_count, 6)

    @patch("builtins.input", side_effect=[
        "  admin@example.com  ",
        "  superadmin  ",
        "  Super  ",
        "  Admin  ",
        "StrongPass@123",
        "  +919876543210  ",
    ])
    def test_create_superadmin_strips_input_fields(self, mock_input):
        User = get_user_model()
        output = StringIO()

        call_command("create_superadmin", stdout=output)

        user = User.objects.get(email="admin@example.com")

        self.assertEqual(user.username, "superadmin")
        self.assertEqual(user.first_name, "Super")
        self.assertEqual(user.last_name, "Admin")
        self.assertEqual(user.phone_number, "+919876543210")

    @patch("builtins.input", side_effect=[
        "admin@example.com",
        "superadmin",
        "Super",
        "Admin",
        "StrongPass@123",
        "+919876543210",
    ])
    def test_create_superadmin_sets_password(self, mock_input):
        User = get_user_model()
        call_command("create_superadmin", stdout=StringIO())

        user = User.objects.get(email="admin@example.com")

        self.assertTrue(user.check_password("StrongPass@123"))


class RedisCacheTests(APITestCase):

    def test_cache_set_and_get(self):
        from django.core.cache import cache

        cache.set("test_key", "Redis is working", timeout=60)

        result = cache.get("test_key")

        self.assertEqual(result, "Redis is working")

    def test_cache_returns_none_for_missing_key(self):
        from django.core.cache import cache

        cache.delete("missing_test_key")

        self.assertIsNone(cache.get("missing_test_key"))

    def test_cache_key_expires(self):
        from django.core.cache import cache

        cache.set("expiring_test_key", "temporary", timeout=0)

        self.assertIsNone(cache.get("expiring_test_key"))