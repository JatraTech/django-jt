from django.conf import settings
from rest_framework.permissions import BasePermission

DEFAULT_ADMIN_ROLES = ("admin",)


def get_admin_roles() -> tuple[str, ...]:
    roles = getattr(settings, "DJANGO_JT_ADMIN_ROLES", None)
    if roles is None:
        return DEFAULT_ADMIN_ROLES
    if isinstance(roles, str):
        return (roles,)
    return tuple(roles)


class AdminOnly(BasePermission):
    """Allow users whose ``user_role`` is in ``settings.DJANGO_JT_ADMIN_ROLES`` (default: admin)."""

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        role = getattr(user, "user_role", None)
        return role in get_admin_roles()
