import requests
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from mozilla_django_oidc.contrib.drf import (
    OIDCAuthentication as MozillaOIDCAuthentication,
)
from mozilla_django_oidc.middleware import SessionRefresh as MozillaSessionRefresh
from rest_framework import status
from rest_framework.exceptions import APIException

from django_jt.auth.defaults import DEFAULT_AUTH901_BASE_URL, _setting

DEFAULT_SERVICE_SCOPES = "openid urn:zitadel:iam:org:project:id:zitadel:aud"
TIMEOUT = 15

__all__ = [
    "Auth901Unavailable",
    "OIDCAuthentication",
    "OIDCBackend",
    "SessionRefresh",
    "invite_user",
]


class Auth901Unavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Auth901 didn't complete that invite."
    default_code = "auth901_unavailable"


def _issuer() -> str:
    return (
        _setting("AUTH901_BASE_URL", DEFAULT_AUTH901_BASE_URL)
        or DEFAULT_AUTH901_BASE_URL
    ).rstrip("/")


def _access_token() -> str:
    client_id = (_setting("AUTH901_SERVICE_CLIENT_ID") or "").strip()
    client_secret = (_setting("AUTH901_SERVICE_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise Auth901Unavailable()
    token_url = f"{_issuer()}/oauth/v2/token"
    scope = (_setting("AUTH901_SERVICE_SCOPES") or DEFAULT_SERVICE_SCOPES).strip()
    try:
        reply = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": scope,
            },
            timeout=TIMEOUT,
        )
        reply.raise_for_status()
        access = (reply.json() or {}).get("access_token")
    except Auth901Unavailable:
        raise
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise Auth901Unavailable() from exc
    if not access:
        raise Auth901Unavailable()
    return access


def invite_user(email: str, given_name: str, family_name: str) -> str:
    """Create a human user in Auth901 and email them an invite. Returns their subject."""
    payload = {
        "username": email,
        "human": {
            "profile": {"givenName": given_name, "familyName": family_name},
            "email": {"email": email, "sendCode": {}},
        },
    }
    organization_id = (_setting("AUTH901_ORGANIZATION_ID") or "").strip()
    if organization_id:
        payload["organizationId"] = organization_id
    token = _access_token()
    try:
        reply = requests.post(
            f"{_issuer()}/v2/users/new",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
        )
        reply.raise_for_status()
        data = reply.json() or {}
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise Auth901Unavailable() from exc
    user_id = data.get("id") or data.get("userId")
    if not user_id:
        raise Auth901Unavailable()
    return str(user_id)


class OIDCBackend(OIDCAuthenticationBackend):
    """Match users on ``auth901_sub``, then email; persist Auth901 claims."""

    def filter_users_by_claims(self, claims):
        sub = claims.get("sub")
        if sub and hasattr(self.UserModel, "auth901_sub"):
            users = self.UserModel.objects.filter(auth901_sub=sub)
            if users.exists():
                return users
        email = claims.get("email")
        if email:
            return self.UserModel.objects.filter(email__iexact=email)
        return self.UserModel.objects.none()

    def create_user(self, claims):
        user = super().create_user(claims)
        return self.update_user(user, claims)

    def update_user(self, user, claims):
        if hasattr(user, "auth901_sub") and claims.get("sub"):
            user.auth901_sub = claims["sub"]
        if claims.get("email"):
            user.email = claims["email"]
        if claims.get("given_name"):
            user.first_name = claims["given_name"]
        if claims.get("family_name"):
            user.last_name = claims["family_name"]
        username = claims.get("preferred_username")
        if username:
            user.username = username[:150]
        user.save()
        return user


class OIDCAuthentication(MozillaOIDCAuthentication):
    """DRF Bearer auth that resolves the user through ``OIDCBackend``."""

    def __init__(self, backend=None):
        super().__init__(backend=backend or OIDCBackend())


class SessionRefresh(MozillaSessionRefresh):
    """Renew an expired Auth901 browser session. Place after AuthenticationMiddleware."""
