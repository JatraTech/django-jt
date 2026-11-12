# Changelog

## 0.3.1

- **Ordering:** `ProximityOrderingFilter` — `?ordering==date_field` for closest date/datetime (PostgreSQL `Extract` epoch); nulls-last on other terms.
- **Pagination:** `StandardLimitOffsetPagination`, `StandardCursorPagination`.
- **Serializers:** `ContentTypeByNameSerializer` (`app_label.model` ↔ `ContentType`).
- **Helpers:** `format_duration_hhmmss`, `format_duration_hhmmday` on package root.
- **Auth901:** `auth901_service_credentials()` falls back to `AUTH901_CLIENT_ID` / `AUTH901_CLIENT_SECRET` when `AUTH901_SERVICE_*` is unset (local shared Casdoor app; prod can still set a dedicated M2M client).
- **Auth901:** Optional `AUTH901_APPLICATION` sets Casdoor `signupApplication` on users created by sync.
- **Auth901:** Sync options are CLI-only (`--initial-password`, `--dry-run`, `--repair`, `--require-password-change`); removed `AUTH901_SYNC_INITIAL_PASSWORD` and `auth901_sync_initial_password()`.

## 0.3.0

- **OIDC:** `auth901_oidc_enabled()` in `auth.defaults` — browser OIDC when `AUTH901_CLIENT_ID` is set and `mozilla_django_oidc` is installed; `apply_oidc_defaults` and `/oidc/` routes gated the same way. JWT hosts leave the client id unset.
- **Email:** Gmail and Microsoft Graph backends, recipient override helper, built-in Celery queue when eager or worker ping succeeds (else sync send), shared tasks, `gmail_oauth_token` / `graph_auth` commands.
- **DRF:** Serializer image URL helpers, `OptimizedImageField` / `images.py`, `validate_app_env` check, `OverrideContentTypeMiddleware`.
- **Analytics** (`analytics` extra, included in `[all]`): `DataType`, pydantic `AnalyticsData` / `AnalyticsDataItem`, `AnalyticsDataViewMixin`, `AnalyticsGraphViewMixin`.
- **Export:** `ExportMixin` (`export/xlsx` via Polars + StyleFrame).
- **Permissions:** `AdminOnly` with `DJANGO_JT_ADMIN_ROLES` (default `admin`).
- **Filters:** `AudienceFilter` for `view.audience_lookups`; `AudienceFilterFn` protocol on `BaseListView`.
- **`[all]` extra:** Pillow, Google client libraries, MSAL, plus analytics deps (pydantic, polars, styleframe).
- **Consumers:** django-template reference host uses this package; product backends can migrate vendored `app.utils` to `django_jt.*` incrementally.
- **Celery email:** `send_gmail_emails` / `send_graph_emails` register in `DjangoJTConfig.ready()`; hosts need not duplicate tasks in `app.tasks`.
- **Health:** `django_jt.health.liveness` and `readiness` (DB + optional Redis broker).
- **OpenAPI UI:** `django_jt.drf.spectacular.SpectacularElementsView` and `SpectacularRapiDocView`.
- **Docs:** Removed unused `unported/` archive (tenancy/L1 snapshots); no API change.

## 0.2.0

- Auth901 sync, invite, Postmaster backend, request id, core DRF mixins.
