SECRET_KEY = "django-jt-tests"
DEBUG = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django_userforeignkey",
    "mozilla_django_oidc",
    "rest_framework",
    "django_jt",
    "tests",
]

ROOT_URLCONF = "tests.urls"

AUTH901_BASE_URL = "https://auth.new901.io"
AUTH901_CLIENT_ID = "test-client-id"
AUTH901_SERVICE_CLIENT_ID = "svc"
AUTH901_SERVICE_CLIENT_SECRET = "secret"

from django_jt.auth.defaults import oidc_defaults

globals().update(oidc_defaults())

AUTH_USER_MODEL = "tests.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

FIELD_ENCRYPTION_KEYS = []
