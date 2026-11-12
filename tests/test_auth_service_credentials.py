import pytest
from django.test import override_settings

import tests.settings as test_settings
from django_jt.auth.base import auth901_service_credentials


def _patch_auth901_creds(monkeypatch, settings, **kwargs):
    for key, value in kwargs.items():
        settings.__setattr__(key, value)
        monkeypatch.setattr(test_settings, key, value)


@override_settings(
    AUTH901_SERVICE_CLIENT_ID="svc-id",
    AUTH901_SERVICE_CLIENT_SECRET="svc-secret",
)
def test_service_credentials_prefer_service_vars(monkeypatch, settings):
    _patch_auth901_creds(
        monkeypatch,
        settings,
        AUTH901_SERVICE_CLIENT_ID="svc-id",
        AUTH901_SERVICE_CLIENT_SECRET="svc-secret",
        AUTH901_CLIENT_ID="oidc-id",
        AUTH901_CLIENT_SECRET="oidc-secret",
    )
    assert auth901_service_credentials() == ("svc-id", "svc-secret")


def test_service_credentials_fallback_to_oidc_client(monkeypatch, settings):
    _patch_auth901_creds(
        monkeypatch,
        settings,
        AUTH901_SERVICE_CLIENT_ID="",
        AUTH901_SERVICE_CLIENT_SECRET="",
        AUTH901_CLIENT_ID="oidc-id",
        AUTH901_CLIENT_SECRET="oidc-secret",
    )
    assert auth901_service_credentials() == ("oidc-id", "oidc-secret")


def test_service_credentials_require_one_pair(monkeypatch, settings):
    _patch_auth901_creds(
        monkeypatch,
        settings,
        AUTH901_SERVICE_CLIENT_ID="",
        AUTH901_SERVICE_CLIENT_SECRET="",
        AUTH901_CLIENT_ID="",
        AUTH901_CLIENT_SECRET="",
    )
    with pytest.raises(ValueError, match="AUTH901_SERVICE_CLIENT_ID"):
        auth901_service_credentials()
