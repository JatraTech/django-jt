SECRET_KEY = "django-jt-tests"
DEBUG = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_userforeignkey",
    "mozilla_django_oidc",
    "django_jt",
    "tests",
]

from django_jt.auth.defaults import oidc_defaults

globals().update(oidc_defaults())
OIDC_RP_CLIENT_ID = "test-client-id"

AUTH_USER_MODEL = "tests.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

FIELD_ENCRYPTION_KEYS = []
