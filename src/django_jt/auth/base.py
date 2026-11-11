"""Shared Auth901 settings helpers for OIDC invite and Casdoor sync."""

from __future__ import annotations

from django_jt.auth.defaults import DEFAULT_AUTH901_BASE_URL, _setting

AUTH901_HTTP_TIMEOUT = 15

__all__ = [
    "AUTH901_HTTP_TIMEOUT",
    "auth901_base_url",
    "auth901_organization",
    "auth901_service_credentials",
    "auth901_sync_initial_password",
    "link_auth901_sub",
]


def auth901_sync_initial_password(*, cli_value: str | None = None) -> str | None:
    """Initial Casdoor password for sync; env ``AUTH901_SYNC_INITIAL_PASSWORD`` wins over CLI."""
    env_value = (_setting("AUTH901_SYNC_INITIAL_PASSWORD") or "").strip()
    if env_value:
        return env_value
    cli = (cli_value or "").strip()
    return cli or None


def auth901_base_url() -> str:
    return (
        _setting("AUTH901_BASE_URL", DEFAULT_AUTH901_BASE_URL) or DEFAULT_AUTH901_BASE_URL
    ).rstrip("/")


def auth901_service_credentials() -> tuple[str, str]:
    client_id = (_setting("AUTH901_SERVICE_CLIENT_ID") or "").strip()
    client_secret = (_setting("AUTH901_SERVICE_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            "AUTH901_SERVICE_CLIENT_ID and AUTH901_SERVICE_CLIENT_SECRET are required."
        )
    return client_id, client_secret


def auth901_organization(*, required: bool = False) -> str:
    org = (
        (_setting("AUTH901_ORGANIZATION") or _setting("AUTH901_ORGANIZATION_ID") or "")
        .strip()
    )
    if required and not org:
        raise ValueError("AUTH901_ORGANIZATION (or AUTH901_ORGANIZATION_ID) is required.")
    return org


def link_auth901_sub(user, sub: str) -> None:
    if hasattr(user, "auth901_sub"):
        user.auth901_sub = sub
        user.save(update_fields=["auth901_sub"])
