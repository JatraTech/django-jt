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
        from django_jt.request_id import connect_request_finished

        connect_request_finished()
        register(check_encryption_keys)
