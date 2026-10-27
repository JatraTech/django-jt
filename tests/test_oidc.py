from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from django_jt.auth.defaults import oidc_defaults, provider_logout
from django_jt.auth.oidc import OIDCAuthentication, OIDCBackend

User = get_user_model()


def test_appconfig_applies_oidc_settings(settings):
    assert settings.OIDC_RP_CLIENT_ID == "test-client-id"
    assert settings.OIDC_OP_BASE_URL == "https://auth.new901.io"
    assert settings.OIDC_USE_PKCE is True
    assert settings.OIDC_DRF_AUTH_BACKEND == "django_jt.auth.oidc.OIDCBackend"


def test_oidc_defaults_auth901():
    values = oidc_defaults()
    assert values["OIDC_OP_BASE_URL"] == "https://auth.new901.io"
    assert values["OIDC_USE_PKCE"] is True
    assert values["OIDC_PKCE_CODE_CHALLENGE_METHOD"] == "S256"
    assert values["OIDC_RP_SIGN_ALGO"] == "RS256"
    assert values["OIDC_OP_AUTHORIZATION_ENDPOINT"] == "https://auth.new901.io/oauth/v2/authorize"
    assert values["OIDC_OP_TOKEN_ENDPOINT"] == "https://auth.new901.io/oauth/v2/token"
    assert values["OIDC_OP_USER_ENDPOINT"] == "https://auth.new901.io/oidc/v1/userinfo"
    assert values["OIDC_OP_JWKS_ENDPOINT"] == "https://auth.new901.io/oauth/v2/keys"
    assert values["OIDC_RP_CLIENT_ID"] != "395373995647565826"
    assert values["OIDC_DRF_AUTH_BACKEND"] == "django_jt.auth.oidc.OIDCBackend"


def test_oidc_defaults_override_base():
    values = oidc_defaults(AUTH901_BASE_URL="https://auth.example.com")
    assert values["OIDC_OP_TOKEN_ENDPOINT"] == "https://auth.example.com/oauth/v2/token"
    assert values["OIDC_OP_JWKS_ENDPOINT"] == "https://auth.example.com/oauth/v2/keys"


def test_oidc_defaults_prefer_env(monkeypatch):
    monkeypatch.setenv("AUTH901_BASE_URL", "https://auth.env.example")
    monkeypatch.setenv("AUTH901_CLIENT_ID", "env-client-id")
    values = oidc_defaults()
    assert values["OIDC_OP_BASE_URL"] == "https://auth.env.example"
    assert values["OIDC_RP_CLIENT_ID"] == "env-client-id"


def test_oidc_defaults_read_loading_settings_module(monkeypatch):
    """environs sets settings attrs without putting them in os.environ."""
    import sys
    import types

    monkeypatch.delenv("AUTH901_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTH901_BASE_URL", raising=False)
    # Settings still loading: LazySettings is not usable yet.
    monkeypatch.setattr(
        "django.conf.settings",
        SimpleNamespace(configured=False),
    )
    module_name = "tests.fake_auth901_settings"
    fake = types.ModuleType(module_name)
    fake.AUTH901_CLIENT_ID = "settings-module-client"
    fake.AUTH901_BASE_URL = "https://auth.settings.example"
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", module_name)
    monkeypatch.setitem(sys.modules, module_name, fake)
    values = oidc_defaults()
    assert values["OIDC_RP_CLIENT_ID"] == "settings-module-client"
    assert values["OIDC_OP_BASE_URL"] == "https://auth.settings.example"


def test_provider_logout_uses_end_session(settings):
    settings.LOGOUT_REDIRECT_URL = "/"
    request = SimpleNamespace(build_absolute_uri=lambda path: f"https://app.example.com{path}")
    url = provider_logout(request)
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.new901.io"
    assert parsed.path == "/oidc/v1/end_session"
    query = parse_qs(parsed.query)
    assert query["post_logout_redirect_uri"] == ["https://app.example.com/"]


@pytest.mark.django_db
def test_filter_users_by_auth901_sub():
    user = User.objects.create_user(username="ada", email="ada@example.com", password="x", auth901_sub="sub-123")
    backend = OIDCBackend()
    matches = backend.filter_users_by_claims({"sub": "sub-123", "email": "other@example.com"})
    assert list(matches) == [user]


@pytest.mark.django_db
def test_filter_users_by_email_fallback():
    user = User.objects.create_user(username="ada", email="ada@example.com", password="x")
    backend = OIDCBackend()
    matches = backend.filter_users_by_claims({"sub": "new-sub", "email": "ada@example.com"})
    assert list(matches) == [user]


@pytest.mark.django_db
def test_update_user_sets_sub_and_names():
    user = User.objects.create_user(username="old", email="old@example.com", password="x")
    backend = OIDCBackend()
    backend.update_user(
        user,
        {
            "sub": "sub-9",
            "email": "new@example.com",
            "given_name": "Ada",
            "family_name": "Lovelace",
            "preferred_username": "ada",
        },
    )
    user.refresh_from_db()
    assert user.auth901_sub == "sub-9"
    assert user.email == "new@example.com"
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.username == "ada"


def test_bearer_authentication_uses_oidc_backend():
    user = User(username="ada", email="ada@example.com")
    auth = OIDCAuthentication()
    assert isinstance(auth.backend, OIDCBackend)
    auth.backend.get_or_create_user = lambda token, id_token, payload: user
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer access-token")
    assert auth.authenticate(request) == (user, "access-token")
