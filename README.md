# django-jt

Reusable Django utilities for JatraTech projects: an Auth901-ready user model, mozilla-django-oidc helpers, model mixins, encrypted fields, pagination, and a Postmaster email backend.

## Install

Source: [github.com/JatraTech/django-jt](https://github.com/JatraTech/django-jt).

In another project:

```text
uv add "django-jt[all] @ git+https://github.com/JatraTech/django-jt.git"
```

In this repo:

```text
uv sync --all-extras --group dev
uv run pytest
```

pip fallback: `pip install -e ".[all]"`.

Optional extras:

| Extra | Adds |
|---|---|
| `models` | `django-userforeignkey` (required by `ModelMixin`) |
| `crypto` | `cryptography` (encrypted fields) |
| `rest` | Django REST framework + django-filter |
| `email` | `requests` (Postmaster backend) |
| `errors` | `drf-standardized-errors` |
| `oidc` | `mozilla-django-oidc` (Auth901 login) |
| `all` | Everything above |

## Custom user model

Subclass `AbstractExtraUser` and set `AUTH_USER_MODEL`. The abstract user keeps Django username login and adds `auth901_sub` for the Auth901 OIDC subject.

```python
# accounts/models.py
from django_jt.auth import AbstractExtraUser


class User(AbstractExtraUser):
    pass
```

```python
# settings.py
AUTH_USER_MODEL = "accounts.User"
INSTALLED_APPS = [
    ...,
    "django_jt",  # optional; enables encryption-key system checks
]
```

`django_jt` ships only abstract models. The host app owns the concrete `User` and its migrations.

## Auth901 / mozilla-django-oidc

Install the `oidc` extra. Defaults assume `OIDC_OP_BASE_URL=https://auth.new901.io` with PKCE (S256) and RS256. **`OIDC_RP_CLIENT_ID` has no package default** — set it in settings or the environment (example: `395373995647565826`).

```python
# settings.py
from django_jt.auth.defaults import oidc_defaults

INSTALLED_APPS = [
    ...,
    "django.contrib.auth",
    "mozilla_django_oidc",
    "django_jt",
]

AUTHENTICATION_BACKENDS = [
    "django_jt.auth.oidc.OIDCBackend",
]

globals().update(oidc_defaults())
# OIDC_RP_CLIENT_ID must be set here or as an env var
```

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("", include("django_jt.urls")),  # /oidc/authenticate/, /oidc/callback/, /oidc/logout/
]
```

`OIDCBackend` looks up users by `auth901_sub`, then email, and writes `sub`, email, and name claims onto the user.

## Request id

Put the middleware first so every response, including errors, carries `X-Request-ID`. A valid incoming id (8–128 letters, digits, `.`, `_`, `:`, `-`) is kept; anything else is replaced.

```python
MIDDLEWARE = ["django_jt.request_id.RequestIdMiddleware", ...]
LOGGING = {
    "filters": {"request_id": {"()": "django_jt.request_id.RequestIdFilter"}},
    "handlers": {"console": {"filters": ["request_id"], ...}},
}
CORS_ALLOW_HEADERS = (..., "x-request-id")
CORS_EXPOSE_HEADERS = (..., "X-Request-ID")
```

`django_jt` in `INSTALLED_APPS` clears the id on `request_finished`. Call `django_jt.request_id.connect_celery()` from the Celery app if background tasks should keep the same id.

## Other utilities

```python
from django_jt.mixins.models import ModelMixin, NameModelMixin, CodeModelMixin
from django_jt.fields import AmountField, EncryptedTextField
from django_jt.pagination import StandardPagination
from django_jt.backends.email.postmaster import PostMasterEmailBackend
```

`ModelMixin` uses `UserForeignKey`. Projects that use it should add `django_userforeignkey` to `INSTALLED_APPS`.

Encrypted fields read `settings.FIELD_ENCRYPTION_KEYS` (a list of Fernet keys). The first key encrypts; every key can decrypt.

## Host-coupled code

Tenant, audit, and blueprint-specific modules live in `unported/` and are not installed. They still depend on host apps such as `tenancy` and `audit`.
