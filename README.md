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

Subclass `Auth901UserMixin` and set `AUTH_USER_MODEL`. The abstract user keeps Django username login and adds `auth901_sub` for the Auth901 OIDC subject.

```python
# accounts/models.py
from django_jt.auth import Auth901UserMixin


class User(Auth901UserMixin):
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

Install the `oidc` extra. Defaults assume `AUTH901_BASE_URL=https://auth.new901.io` with PKCE (S256) and RS256. **`AUTH901_CLIENT_ID` has no package default** — set it in settings or the environment (example: `395373995647565826`).

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "django.contrib.auth",
    "mozilla_django_oidc",
    "django_jt",  # applies OIDC_* from AUTH901_* in AppConfig.ready()
]

AUTHENTICATION_BACKENDS = [
    "django_jt.auth.oidc.OIDCBackend",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "django_jt.auth.oidc.OIDCAuthentication",
    ],
}

AUTH901_BASE_URL = env("AUTH901_BASE_URL", default="https://auth.new901.io")
AUTH901_CLIENT_ID = env("AUTH901_CLIENT_ID")
```

`SessionRefresh` must follow session and authentication middleware. After `oidc_id_token_expiration`, a browser GET redirects to Auth901 with `prompt=none`. An `XMLHttpRequest` gets `403` and `refresh_url`. Renew waits `OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS` (15 minutes unless you set it).

```python
MIDDLEWARE = [
    "django_jt.request_id.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_jt.auth.oidc.SessionRefresh",
]
```

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path("", include("django_jt.urls")),  # /oidc/authenticate/, /oidc/callback/, /oidc/logout/
]
```

`OIDCBackend` looks up users by `auth901_sub`, then email, and writes `sub`, email, and name claims onto the user.

`POST /auth/invite/` (signed in) creates the person in Auth901 and emails them an invite. Install the `rest` extra. A service account calls Auth901; set these in settings or the environment:

```python
AUTH901_SERVICE_CLIENT_ID = "..."
AUTH901_SERVICE_CLIENT_SECRET = "..."
AUTH901_ORGANIZATION_ID = "..."  # optional
```

Body: `{"email", "given_name", "family_name"}`. The answer is `201 {"id", "email"}`, and the local user stores `id` on `auth901_sub`.

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
