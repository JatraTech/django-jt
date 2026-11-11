import django_jt
from django_jt.auth import Auth901UserMixin
from django_jt.auth.defaults import oidc_defaults


def test_package_version():
    assert django_jt.__version__ == "0.2.0"


def test_auth_exports():
    assert Auth901UserMixin is not None
    assert callable(oidc_defaults)
