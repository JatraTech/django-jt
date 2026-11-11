"""Casdoor admin API, provisioning, and bulk sync to backfill ``auth901_sub``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
import requests

from django_jt.auth.base import (
    AUTH901_HTTP_TIMEOUT,
    auth901_base_url,
    auth901_organization,
    auth901_service_credentials,
    link_auth901_sub,
)
from django_jt.auth.defaults import _setting

DEFAULT_SERVICE_SCOPE = "openid"
_casdoor_token: str | None = None

@dataclass(frozen=True, slots=True)
class SyncPasswordOptions:
    initial_password: str | None
    require_password_change: bool = False


__all__ = [
    "Auth901Error",
    "SyncOutcome",
    "SyncPasswordOptions",
    "find_user_by_email",
    "organization",
    "provision_user",
    "reset_casdoor_token",
    "sync_user",
]


class Auth901Error(Exception):
    """Auth901 admin API call failed."""


def reset_casdoor_token() -> None:
    """Clear cached Casdoor client-credentials token (e.g. at start of management command)."""
    global _casdoor_token
    _casdoor_token = None


def organization() -> str:
    try:
        return auth901_organization(required=True)
    except ValueError as exc:
        raise Auth901Error(str(exc)) from exc


def _service_token() -> str:
    global _casdoor_token
    if _casdoor_token:
        return _casdoor_token
    try:
        client_id, client_secret = auth901_service_credentials()
    except ValueError as exc:
        raise Auth901Error(str(exc)) from exc
    scope = (_setting("AUTH901_SERVICE_SCOPES") or DEFAULT_SERVICE_SCOPE).strip() or DEFAULT_SERVICE_SCOPE
    token_url = f"{auth901_base_url()}/api/login/oauth/access_token"
    try:
        reply = requests.post(
            token_url,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials", "scope": scope},
            timeout=AUTH901_HTTP_TIMEOUT,
        )
        reply.raise_for_status()
        access = (reply.json() or {}).get("access_token")
    except Auth901Error:
        raise
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise Auth901Error("Could not obtain Auth901 service token.") from exc
    if not access:
        raise Auth901Error("Auth901 token response did not include access_token.")
    _casdoor_token = access
    return access


def _casdoor_request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
) -> dict:
    token = _service_token()
    url = f"{auth901_base_url()}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        reply = requests.request(
            method, url, params=params, json=json, headers=headers, timeout=AUTH901_HTTP_TIMEOUT
        )
        reply.raise_for_status()
        return reply.json() or {}
    except Auth901Error:
        raise
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise Auth901Error(f"Auth901 {method} {path} failed.") from exc


def _casdoor_ok_data(payload: dict) -> list:
    if (payload or {}).get("status") != "ok":
        msg = (payload or {}).get("msg") or "Auth901 request failed."
        raise Auth901Error(str(msg))
    data = payload.get("data")
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _casdoor_sub(user: dict) -> str:
    sub = (user.get("id") or "").strip()
    if not sub:
        raise Auth901Error("Auth901 user record is missing id (OIDC sub).")
    return sub


def _casdoor_name_from_string(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"[^\w.\-@+]", "_", text)
    return (text[:60] or "").strip("_")


def _casdoor_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return _casdoor_name_from_string(local) or "user"


def _casdoor_name_for_user(user, email: str) -> str:
    username = (getattr(user, "username", None) or "").strip()
    from_username = _casdoor_name_from_string(username)
    if from_username:
        return from_username
    return _casdoor_name_from_email(email)


def _sync_profile_from_user(user, *, casdoor_name: str) -> tuple[str, str, str]:
    given = (getattr(user, "first_name", None) or "").strip()
    family = (getattr(user, "last_name", None) or "").strip()
    full_name = ""
    if hasattr(user, "name"):
        full_name = (getattr(user, "name", None) or "").strip()
    if not given and not family and full_name:
        parts = full_name.split(None, 1)
        given = parts[0] if parts else ""
        family = parts[1] if len(parts) > 1 else ""
    display = " ".join(part for part in (given, family) if part).strip() or full_name or casdoor_name
    return given, family, display


def _add_user_name_taken(msg: str) -> bool:
    text = (msg or "").lower()
    if "email" in text and "exist" in text:
        return False
    return "exist" in text and ("name" in text or "user" in text)


def find_user_by_email(email: str) -> dict | None:
    """Return the Casdoor user dict for ``email`` in the configured org, or None."""
    normalized = (email or "").strip()
    if not normalized:
        return None
    params = {
        "owner": organization(),
        "field": "email",
        "value": normalized,
        "p": "1",
        "pageSize": "1",
    }
    users = _casdoor_ok_data(_casdoor_request("GET", "/api/get-users", params=params))
    for user in users:
        if not isinstance(user, dict):
            continue
        remote_email = (user.get("email") or "").strip()
        if remote_email.lower() == normalized.lower():
            return user
    return None


def _add_casdoor_user(
    email: str,
    *,
    casdoor_name: str,
    given_name: str,
    family_name: str,
    display_name: str,
    password_options: SyncPasswordOptions | None = None,
) -> None:
    owner = organization()
    payload: dict = {
        "owner": owner,
        "name": casdoor_name,
        "email": email.strip(),
        "firstName": (given_name or "").strip(),
        "lastName": (family_name or "").strip(),
        "displayName": (display_name or casdoor_name).strip(),
        "type": "normal-user",
    }
    application = (_setting("AUTH901_APPLICATION") or "").strip()
    if application:
        payload["signupApplication"] = application
    if password_options and password_options.initial_password:
        payload["password"] = password_options.initial_password
        if password_options.require_password_change:
            payload["needUpdatePassword"] = True

    body = _casdoor_request("POST", "/api/add-user", json=payload)
    if body.get("status") == "ok":
        return

    msg = (body.get("msg") or "Auth901 add-user failed.").strip()
    fallback = _casdoor_name_from_email(email)
    if _add_user_name_taken(msg) and casdoor_name != fallback:
        payload["name"] = fallback
        payload["displayName"] = (display_name or fallback).strip()
        body = _casdoor_request("POST", "/api/add-user", json=payload)
        if body.get("status") == "ok":
            return
        msg = (body.get("msg") or msg).strip()
    raise Auth901Error(msg)


def provision_user(
    email: str,
    *,
    casdoor_name: str,
    given_name: str,
    family_name: str,
    display_name: str,
    password_options: SyncPasswordOptions | None = None,
) -> tuple[str, bool, dict | None]:
    """Ensure Casdoor has this person. Returns ``(sub, created, remote_or_none)``."""
    existing = find_user_by_email(email)
    if existing:
        return _casdoor_sub(existing), False, existing

    _add_casdoor_user(
        email,
        casdoor_name=casdoor_name,
        given_name=given_name,
        family_name=family_name,
        display_name=display_name,
        password_options=password_options,
    )
    created = find_user_by_email(email)
    if not created:
        raise Auth901Error("Auth901 user was not found after add-user.")
    return _casdoor_sub(created), True, created


def _provision_user_from_local(
    user,
    email: str,
    password_options: SyncPasswordOptions | None = None,
) -> tuple[str, bool, dict | None]:
    casdoor_name = _casdoor_name_for_user(user, email)
    given, family, display = _sync_profile_from_user(user, casdoor_name=casdoor_name)
    return provision_user(
        email,
        casdoor_name=casdoor_name,
        given_name=given,
        family_name=family,
        display_name=display,
        password_options=password_options,
    )


class SyncOutcome(str, Enum):
    SKIPPED_LINKED = "skipped_linked"
    SKIPPED_NO_EMAIL = "skipped_no_email"
    SKIPPED_NO_FIELD = "skipped_no_field"
    LINKED_EXISTING = "linked_existing"
    CREATED = "created"
    RELINKED = "relinked"
    RECREATED = "recreated"
    ERROR = "error"


def sync_user(
    user,
    *,
    dry_run: bool = False,
    repair: bool = False,
    password_options: SyncPasswordOptions | None = None,
) -> SyncOutcome:
    """Push one local user to Auth901 when ``auth901_sub`` is missing.

    With ``repair=True``, re-check users that already have ``auth901_sub`` (email lookup)
    and relink or recreate Casdoor rows when IdP records were deleted or replaced.
    """
    if not hasattr(user, "auth901_sub"):
        return SyncOutcome.SKIPPED_NO_FIELD

    local_sub = (user.auth901_sub or "").strip()
    email = (getattr(user, "email", None) or "").strip()
    if not email:
        return SyncOutcome.SKIPPED_NO_EMAIL

    if local_sub and not repair:
        return SyncOutcome.SKIPPED_LINKED

    if repair:
        try:
            remote = find_user_by_email(email)
        except Auth901Error:
            return SyncOutcome.ERROR

        if remote:
            remote_sub = _casdoor_sub(remote)
            if remote_sub == local_sub:
                return SyncOutcome.SKIPPED_LINKED
            if dry_run:
                return SyncOutcome.RELINKED
            link_auth901_sub(user, remote_sub)
            return SyncOutcome.RELINKED

        if dry_run:
            return SyncOutcome.RECREATED
        try:
            sub, _created, _remote = _provision_user_from_local(user, email, password_options)
        except Auth901Error:
            return SyncOutcome.ERROR
        link_auth901_sub(user, sub)
        return SyncOutcome.RECREATED

    if dry_run:
        try:
            remote = find_user_by_email(email)
        except Auth901Error:
            return SyncOutcome.ERROR
        if remote:
            return SyncOutcome.LINKED_EXISTING
        return SyncOutcome.CREATED

    try:
        sub, created, _remote = _provision_user_from_local(user, email, password_options)
    except Auth901Error:
        return SyncOutcome.ERROR

    link_auth901_sub(user, sub)
    return SyncOutcome.CREATED if created else SyncOutcome.LINKED_EXISTING
