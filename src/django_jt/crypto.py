"""
Symmetric encryption for secrets and sensitive fields (OAuth tokens, two-factor
secrets, regulated client data).

Keys come from ``settings.FIELD_ENCRYPTION_KEYS`` (a list or comma-separated
Fernet keys). The first key encrypts; every key can decrypt, so rotation is:
add a new key at the front, re-save rows, then drop the old key.

In tests and local development without keys, a fixed development key is used
and a warning is logged once. Production should set keys; ``django_jt`` emits
system check ``django_jt.W001`` when they are missing and ``DEBUG`` is False.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

logger = logging.getLogger("django_jt.crypto")

_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"new901-platform-development-only").digest())


def _key_list() -> list[str]:
    raw = getattr(settings, "FIELD_ENCRYPTION_KEYS", [])
    if isinstance(raw, str):
        raw = raw.split(",")
    return [k.strip() for k in raw if k and str(k).strip()]


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    keys = _key_list()
    if not keys:
        logger.warning("FIELD_ENCRYPTION_KEYS is empty; using the development key. Never do this in production.")
        keys = [_DEV_KEY.decode()]
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


def reset_cache() -> None:
    _fernet.cache_clear()


def encrypt_str(value: str) -> str:
    if value is None or value == "":
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_str(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - indicates a key problem
        raise ValueError("Cannot decrypt value: wrong or missing FIELD_ENCRYPTION_KEYS.") from exc


def encrypt_json(value) -> str:
    if value in (None, {}, []):
        return ""
    return encrypt_str(json.dumps(value, separators=(",", ":"), sort_keys=True, default=str))


def decrypt_json(token: str, default=None):
    if not token:
        return {} if default is None else default
    return json.loads(decrypt_str(token))


def blind_index(value: str, *, purpose: str) -> str:
    """Deterministic keyed hash for exact-match lookups on encrypted values."""
    from django.conf import settings as s

    key = (s.SECRET_KEY + ":" + purpose).encode("utf-8")
    return hashlib.blake2b((value or "").strip().lower().encode("utf-8"), key=key[:64], digest_size=20).hexdigest()
