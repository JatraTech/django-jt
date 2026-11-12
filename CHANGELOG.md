# Changelog

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
