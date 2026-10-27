import os
from urllib.parse import urlencode

DEFAULT_AUTH901_BASE_URL = "https://auth.new901.io"

__all__ = [
    "DEFAULT_AUTH901_BASE_URL",
    "oidc_defaults",
    "provider_logout",
]


def _setting(name, default=None):
    env_value = os.getenv(name)
    if env_value not in (None, ""):
        return env_value
    try:
        from django.conf import settings

        if settings.configured:
            value = getattr(settings, name, None)
            if value not in (None, ""):
                return value
    except Exception:
        pass
    return default


def oidc_defaults(**overrides) -> dict:
    """mozilla-django-oidc settings for Auth901 (PKCE + RS256).

    ``AUTH901_CLIENT_ID`` is required from settings or env — there is no package default.
    """
    base = (
        overrides.pop("AUTH901_BASE_URL", None)
        or _setting("AUTH901_BASE_URL", DEFAULT_AUTH901_BASE_URL)
        or DEFAULT_AUTH901_BASE_URL
    ).rstrip("/")
    defaults = {
        "OIDC_OP_BASE_URL": base,
        "OIDC_OP_AUTHORIZATION_ENDPOINT": f"{base}/oauth/v2/authorize",
        "OIDC_OP_TOKEN_ENDPOINT": f"{base}/oauth/v2/token",
        "OIDC_OP_USER_ENDPOINT": f"{base}/oidc/v1/userinfo",
        "OIDC_OP_JWKS_ENDPOINT": f"{base}/oauth/v2/keys",
        "OIDC_RP_SIGN_ALGO": "RS256",
        "OIDC_USE_PKCE": True,
        "OIDC_PKCE_CODE_CHALLENGE_METHOD": "S256",
        "OIDC_RP_SCOPES": "openid email profile",
        "OIDC_RP_CLIENT_ID": _setting("AUTH901_CLIENT_ID", ""),
        "OIDC_RP_CLIENT_SECRET": _setting("OIDC_RP_CLIENT_SECRET", ""),
        "OIDC_OP_LOGOUT_URL_METHOD": "django_jt.auth.defaults.provider_logout",
        "OIDC_DRF_AUTH_BACKEND": "django_jt.auth.oidc.OIDCBackend",
    }
    defaults.update(overrides)
    return defaults


def provider_logout(request) -> str:
    """Redirect to Auth901 end-session after the Django session is cleared."""
    from django.conf import settings

    base = (
        _setting("AUTH901_BASE_URL", DEFAULT_AUTH901_BASE_URL) or DEFAULT_AUTH901_BASE_URL
    ).rstrip("/")
    redirect = getattr(settings, "LOGOUT_REDIRECT_URL", "/")
    post_logout = (
        request.build_absolute_uri(redirect)
        if str(redirect).startswith("/")
        else redirect
    )
    params = {
        "client_id": _setting("AUTH901_CLIENT_ID", "") or "",
        "post_logout_redirect_uri": post_logout,
    }
    return f"{base}/oidc/v1/end_session?{urlencode(params)}"
