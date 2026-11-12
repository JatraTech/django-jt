# Unported host-coupled modules

These files still import host apps (`tenancy`, `user`, `access`, `audit`, `blueprint`, `app.constants`) and are **not** part of the installed `django-jt` package.

**Ported to the package (0.3.0+):** analytics validators/mixins, `ExportMixin`, and `AdminOnly` — use `django_jt.analytics`, `django_jt.mixins.analytics`, `django_jt.mixins.export`, and `django_jt.permissions` instead of copying from here.

Remaining snapshots (`mixins/tenant_views.py`, `layer1_api.py`, duplicate `mixins/views.py`, etc.) stay until tenancy and domain imports are rewritten.
