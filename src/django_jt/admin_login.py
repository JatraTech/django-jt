"""Auth901 OIDC admin login template (Backstage or stock fallback)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from django_jt.auth.defaults import auth901_oidc_enabled

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

__all__ = [
    "backstage_available",
    "oidc_admin_login_templates_dir",
    "prepend_oidc_admin_login_templates",
]


def backstage_available() -> bool:
    try:
        import backstage  # noqa: F401
    except ImportError:
        return False
    return True


def oidc_admin_login_templates_dir() -> Path:
    return _TEMPLATES_DIR


def prepend_oidc_admin_login_templates() -> None:
    if not auth901_oidc_enabled():
        return
    if not settings.configured:
        return
    backends = settings.TEMPLATES
    if not backends:
        return
    primary = backends[0]
    dirs = list(primary.get("DIRS", []))
    path = str(_TEMPLATES_DIR)
    if path in dirs:
        return
    dirs.insert(0, path)
    primary["DIRS"] = dirs
