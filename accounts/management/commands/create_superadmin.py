from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        email = input("Email: ").strip()
        username = input("Username: ").strip()
        first_name = input("First name: ").strip()
        last_name = input("Last name: ").strip()
        password = input("Password: ")
        phone_number = input("Phone number: ").strip()

        user = User.objects.create_user(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            password=password,
            phone_number=phone_number,
        )

        user.is_admin = True
        user.is_staff = True
        user.is_superadmin = True
        user.is_active = True

        user.save(
            update_fields=[
                'is_admin',
                'is_staff',
                'is_superadmin',
                'is_active',
            ]
        )

        self.stdout.write(
            self.style.SUCCESS("Super Admin created successfully.")
        )