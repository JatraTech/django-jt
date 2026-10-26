from rest_framework.permissions import BasePermission

from user.constants import UserRoleChoices


class AdminOnly(BasePermission):
    """
    Permission class to allow only admin users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_role == UserRoleChoices.ADMIN
