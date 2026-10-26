import django_jt
from django_jt.auth import AbstractExtraUser
from django_jt.auth.defaults import oidc_defaults


def test_package_version():
    assert django_jt.__version__


def test_auth_exports():
    assert AbstractExtraUser is not None
    assert callable(oidc_defaults)
