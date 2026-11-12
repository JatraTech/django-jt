from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.test import override_settings

from django_jt.permissions import AdminOnly, get_admin_roles


def test_get_admin_roles_default():
    assert get_admin_roles() == ("admin",)


@override_settings(DJANGO_JT_ADMIN_ROLES=["admin", "super_admin"])
def test_get_admin_roles_from_settings():
    assert get_admin_roles() == ("admin", "super_admin")


def test_admin_only_denies_anonymous():
    perm = AdminOnly()
    request = MagicMock()
    request.user = SimpleNamespace(is_authenticated=False)
    assert perm.has_permission(request, None) is False


def test_admin_only_allows_configured_role():
    perm = AdminOnly()
    request = MagicMock()
    request.user = SimpleNamespace(is_authenticated=True, user_role="admin")
    assert perm.has_permission(request, None) is True


def test_admin_only_denies_other_roles():
    perm = AdminOnly()
    request = MagicMock()
    request.user = SimpleNamespace(is_authenticated=True, user_role="user")
    assert perm.has_permission(request, None) is False
