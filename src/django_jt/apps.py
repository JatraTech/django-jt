from django.apps import AppConfig
from django.core.checks import Warning, register


def check_encryption_keys(app_configs, **kwargs):
    from django.conf import settings

    if getattr(settings, "DEBUG", False):
        return []
    raw = getattr(settings, "FIELD_ENCRYPTION_KEYS", [])
    if isinstance(raw, str):
        raw = raw.split(",")
    keys = [k.strip() for k in raw if k and str(k).strip()]
    if keys:
        return []
    return [
        Warning(
            "FIELD_ENCRYPTION_KEYS is empty. Encrypted fields will use the development key.",
            hint="Set FIELD_ENCRYPTION_KEYS to a list of Fernet keys before deploying.",
            id="django_jt.W001",
        )
    ]


class DjangoJTConfig(AppConfig):
    name = "django_jt"
    verbose_name = "Django JT"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import django_jt.checks  # noqa: F401 — register validate_app_env
        from django_jt.auth.defaults import apply_oidc_defaults, auth901_oidc_enabled
        from django_jt.request_id import connect_request_finished

        if auth901_oidc_enabled():
            apply_oidc_defaults()
        connect_request_finished()
        register(check_encryption_keys)
        import django_jt.backends.email.tasks  # noqa: F401 — register Celery email tasks
