from rest_framework.permissions import BasePermission

class IsCustomer(BasePermission):
    """
    Custom permission class to strictly validate if the logged-in user 
    is a Customer. Vendors and Admins will be blocked.
    """
    message = "Access denied. Only customers are allowed to perform this action."

    def has_permission(self, request, view):
        # Check if user is authenticated and has the 'CUSTOMER' role
        # Assuming User.CUSTOMER is defined in your accounts/models.py (e.g., role = 1)
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == request.user.CUSTOMER 
        )