# django-jt

Reusable Django utilities for JatraTech projects: an Auth901-ready user model, mozilla-django-oidc helpers, model mixins, encrypted fields, pagination, and a Postmaster email backend.

## Install

Source: [github.com/JatraTech/django-jt](https://github.com/JatraTech/django-jt).

In another project:

```text
uv add "django-jt[all] @ git+https://github.com/JatraTech/django-jt.git"
```

A specific branch or tag (e.g. after a release):

```text
uv add "django-jt[all] @ git+https://github.com/JatraTech/django-jt.git@v0.3.0"
```

**Office default:** install `django-jt[all]` once; enable only the features you wire in settings (see [Feature recipes](#feature-recipes)).

**Releasing 0.3.0+ (maintainers):** tag `v0.3.0` on the django-jt repo after merge. In consuming apps (new901-admin, condhoa-backend, etc.) run `uv lock --upgrade-package django-jt` or pin the git URL with `@v0.2.0`, then reinstall so `sync_auth901_users` and org fail-fast apply.

## Development

Clone this repository:

```text
uv sync --all-extras --group dev
```

## Verification

```text
uv run pytest -q
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
| `analytics` | `pydantic`, `polars`, `styleframe` (analytics payloads + XLSX export) |
| `all` | Everything above, plus Pillow, Google Gmail API, MSAL (Graph mail), and analytics deps |

## Feature recipes

Install is the same for every profile: **`django-jt[all]`**. Runtime wiring picks what runs.

| Profile | Enable |
|--------|--------|
| **DRF mixins only** | Import `django_jt.mixins.*`, `pagination`, `filters`; no Auth901 settings |
| **JWT / no Auth901** | Leave `AUTH901_CLIENT_ID` unset; do not include `django_jt.urls` for OIDC; optional `AUTHENTICATION_BACKENDS = ["django_jt.backends.authentication.StatusBackend"]` for Django admin session login |
| **Auth901 browser login** | `mozilla_django_oidc` in `INSTALLED_APPS`, `AUTH901_CLIENT_ID`, backends, `include("django_jt.urls")` |
| **Postmaster mail** | `EMAIL_BACKEND = "django_jt.backends.email.postmaster.PostMasterEmailBackend"` |
| **Gmail API** | Same backend path pattern: `django_jt.backends.email.gmail.GmailBackend`; `manage.py gmail_oauth_token` |
| **Microsoft Graph** | `django_jt.backends.email.graph.GraphEmailBackend`; `manage.py graph_auth` |
| **Request id** | `django_jt.request_id.RequestIdMiddleware` + log filter |
| **Audience-scoped lists** | `REST_FRAMEWORK["DEFAULT_FILTER_BACKENDS"]` includes `django_jt.filters.AudienceFilter`; set `audience_lookups` on viewsets |
| **Analytics / XLSX export** | `from django_jt.analytics import AnalyticsData`; mixins in `django_jt.mixins.analytics` and `django_jt.mixins.export` |
| **Legacy admin gate** | `django_jt.permissions.AdminOnly`; optional `DJANGO_JT_ADMIN_ROLES = ["admin", "super_admin"]` |

Async outbound mail (optional): Gmail/Graph queue when `CELERY_TASK_ALWAYS_EAGER` is set or a Celery worker responds to ping; otherwise the web process sends synchronously. Celery tasks `django_jt.backends.email.tasks.send_gmail_emails` / `send_graph_emails` register when `django_jt` is in `INSTALLED_APPS` (no host `app.tasks` mirror required). Workers must load Django (`DJANGO_SETTINGS_MODULE`) so `DjangoJTConfig.ready()` runs.

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

Install the `oidc` extra (included in `[all]`). Defaults assume `AUTH901_BASE_URL=https://auth.new901.io` with PKCE (S256) and RS256. **`AUTH901_CLIENT_ID` has no package default** — set it in settings or the environment (example: `395373995647565826`).

OIDC settings are applied from `AUTH901_*` only when **`AUTH901_CLIENT_ID`** is set and `mozilla_django_oidc` is installed. JWT-only hosts leave the client id unset.

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
AUTH901_CLIENT_SECRET = env("AUTH901_CLIENT_SECRET", default="")
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

`POST /auth/invite/` (signed in) creates the person in Auth901 via `django_jt.auth.oidc.invite_user` and emails them an invite. Install the `rest` extra. A service account calls Auth901; set these in settings or the environment:

```python
AUTH901_SERVICE_CLIENT_ID = "..."
AUTH901_SERVICE_CLIENT_SECRET = "..."
AUTH901_ORGANIZATION_ID = "..."  # optional; or AUTH901_ORGANIZATION (see django_jt.auth.base)
```

Body: `{"email", "given_name", "family_name"}`. The answer is `201 {"id", "email"}`, and the local user stores `id` on `auth901_sub`.

Invite and sync both read organization from **`AUTH901_ORGANIZATION` or `AUTH901_ORGANIZATION_ID`** via `django_jt.auth.base.auth901_organization`. Bulk sync **requires** organization (the command fails fast if it is missing).

**`AUTH901_SERVICE_SCOPES`:** invite (`oidc.invite_user`, `/oauth/v2/token`) and bulk sync (Casdoor `/api/login/oauth/access_token`) read the same setting. If it is unset, invite defaults to a Zitadel-style scope string and sync defaults to `openid`. Set one scope only when it works for both token endpoints in your Auth901 deployment.

### Bulk sync to Auth901 (Casdoor admin API)

Separate from invite/OIDC: `django_jt.auth.auth901_sync` and `manage.py sync_auth901_users` use Casdoor `/api/get-users` and `/api/add-user` via `provision_user` (one lookup when linking, two when creating). They do not change `oidc.invite_user`.

Requires a machine client with permission to those APIs (delegated admin or equivalent), plus:

```python
AUTH901_SERVICE_CLIENT_ID = "..."
AUTH901_SERVICE_CLIENT_SECRET = "..."
AUTH901_ORGANIZATION = "new901"  # or AUTH901_ORGANIZATION_ID (same as invite)
AUTH901_APPLICATION = "hrm"  # optional; signupApplication on new users
```

For users who exist locally but have not signed in with OIDC yet:

```text
python manage.py sync_auth901_users
python manage.py sync_auth901_users --dry-run
python manage.py sync_auth901_users --include-inactive
python manage.py sync_auth901_users --repair
```

### Initial Casdoor password (optional)

Sync does **not** copy Django password hashes. To set a shared initial password in Auth901 (dev/migration), use env or CLI (env wins):

```text
export AUTH901_SYNC_INITIAL_PASSWORD='your-dev-password'
python manage.py sync_auth901_users --require-password-change
```

| Flag | Effect |
|------|--------|
| (default) | New Casdoor users get the initial password on `add-user` when configured; existing Auth901 users are unchanged |
| `--require-password-change` | Sets `needUpdatePassword` on `add-user` when an initial password is set |

Do not commit `AUTH901_SYNC_INITIAL_PASSWORD`. Prefer env over `--initial-password` (shell history). Use `--require-password-change` outside local dev when everyone shares one initial password.

By default the command processes **active** users with a non-empty email and a blank `auth901_sub`. It looks up Auth901 by **email** before creating anyone, so the same person synced from two apps gets the **same** `auth901_sub` when they already exist in Auth901. **First project wins:** only the first create sets Casdoor login **`name`** (from the Django **`username`**, sanitized) and profile (`first_name`/`last_name`, or a single `name` field split for display). A later app sync only backfills local `auth901_sub` and does not call `update-user` on Auth901. If Casdoor rejects a taken `name`, sync retries once with the email local-part. OIDC login still links users on first sign-in; sync is for backfill and migration.

Users already in Auth901 with an old naming scheme (for example Casdoor `name` from email only) are not renamed by default sync or `--repair` when the email still matches; fix in the Auth901 UI or delete the Casdoor user and run `--repair` to recreate with current rules.

If someone is removed from Auth901 but the project still has `auth901_sub`, default sync reports **`skipped_linked`** and does not fix them. Use **`--repair`** after IdP deletes: each linked user gets an email lookup—relink when Casdoor has a new `id`, recreate when the email is missing in Auth901 (one extra lookup per user already linked). OIDC login can also refresh `auth901_sub` via email match when the user signs in again.

Browser login uses Casdoor-shaped OIDC endpoints from `defaults.py`; invite uses the service API implemented in `oidc.py` — your Auth901 deployment may expose both until admin APIs are unified.

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
from django_jt.fields import AmountField, EncryptedTextField, OptimizedImageField
from django_jt.pagination import StandardPagination
from django_jt.backends.email.postmaster import PostMasterEmailBackend
from django_jt.middleware import OverrideContentTypeMiddleware
```

`ModelMixin` uses `UserForeignKey`. Projects that use it should add `django_userforeignkey` to `INSTALLED_APPS`.

## Postmaster email backend

`PostMasterEmailBackend` (`django_jt.backends.email.postmaster`) posts to Postmaster `POST /api/v1/emails/` using a client-credentials token from `POST /api/v1/token/`. Configure `POSTMASTER_URI`, `POSTMASTER_CLIENT_ID`, and `POSTMASTER_CLIENT_SECRET`.

- **Shared / application mailboxes (empty *User sub* in Postmaster):** leave `PostMasterEmailBackend.user_sub` unset. Set `EmailMessage` / `send_mail` **`from_email`** to the mailbox address you configured on the SMTP row; the backend sends it as `provider_sender_email` so Postmaster picks that row in the shared pool. If `from_email` is unset, Postmaster uses the application **default** provider.
- **Optional `provider_name`:** set a non-standard attribute on the message, e.g. `msg.provider_name = "YMCA President"`, to send Postmaster’s `provider_name` hint (case-insensitive match to the SMTP row’s *Name*). When combined with `from_email`, Postmaster requires **both** hints to match the same row (AND).
- **One IdP user's bucket:** set `PostMasterEmailBackend.user_sub` to that user's subject. Optional `from_email` / `provider_name` still narrow the row within that bucket.

Requires the `email` extra (`requests`).

## Gmail and Graph email

See `django_jt.backends.email.gmail` and `django_jt.backends.email.graph`. Management commands: `gmail_oauth_token`, `graph_auth`. Celery tasks live in `django_jt.backends.email.tasks` and register via `DjangoJTConfig.ready()`.

## Health and OpenAPI UI

- **Probes:** `django_jt.health.liveness` and `django_jt.health.readiness` — wire in root `urls.py`, e.g. `path("healthz", liveness)` (optional `readiness` for k8s).
- **Schema browsers:** `django_jt.drf.spectacular.SpectacularElementsView` and `SpectacularRapiDocView` (host still provides `elements.html` / `rapidoc.html` templates).

Encrypted fields read `settings.FIELD_ENCRYPTION_KEYS` (a list of Fernet keys). The first key encrypts; every key can decrypt.

## Host-coupled code

Tenant, audit, and blueprint-specific modules live in `unported/` and are not installed. They still depend on host apps such as `tenancy` and `audit`.
