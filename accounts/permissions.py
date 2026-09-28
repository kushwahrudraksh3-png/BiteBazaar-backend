from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.is_superadmin
            and request.user.is_active
        )
        


class IsAdminOrSuperAdmin(BasePermission):

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.is_active
            and (
                request.user.is_admin
                or request.user.is_superadmin
            )
        )