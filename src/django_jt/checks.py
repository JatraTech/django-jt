"""Deploy-time Django system checks."""

from django.conf import settings
from django.core.checks import Error, register

_APP_ENV_VALUES = frozenset({"local", "staging", "production"})


@register()
def validate_app_env(app_configs, **kwargs):
    if getattr(settings, "SKIP_CONFIG_VALIDATION", False) and settings.DEBUG:
        return []
    out = []
    app_env = (getattr(settings, "APP_ENV", "") or "").strip().lower()
    if app_env not in _APP_ENV_VALUES:
        out.append(
            Error(
                f"APP_ENV={app_env!r} is invalid.",
                hint="Set APP_ENV to local, staging, or production.",
                id="django_jt.E040",
            )
        )
        return out
    if app_env == "production":
        if getattr(settings, "DEMO_ENABLED", False):
            out.append(
                Error(
                    "DEMO_ENABLED must be off when APP_ENV=production.",
                    id="django_jt.E041",
                )
            )
        if settings.DEBUG:
            out.append(
                Error(
                    "DEBUG must be off when APP_ENV=production.",
                    id="django_jt.E042",
                )
            )
    return out
