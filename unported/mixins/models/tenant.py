"""
Tenant-aware versions of the template's base models.

Every model that holds a client business's data extends ``TenantModel`` (or
``TenantNameModel`` / ``TenantNumberedModel``). That gives it:

* the template's audit fields (created_by, updated_by, created_at, updated_at, is_active),
* a ``tenant`` foreign key filled in automatically from the current tenant,
* ``objects``: only the current tenant's rows (``all_active()`` etc. still work),
* ``unscoped``: no application filter. Use it ONLY for class-level DRF
  ``queryset`` declarations (the viewset re-applies the tenant filter) and inside
  ``system_context``. Postgres row-level security still applies either way.

Remember the matching migration operation, ``EnableTenantRLS("<Model>")``.
"""

from __future__ import annotations

from django.db import models

from app.utils.mixins.models import ModelManager, ModelMixin, ModelQuerySet
from tenancy.models.base import TenantScopedManagerMixin, TenantScopedModel, UnscopedManager
from tenancy.services import next_number


class TenantModelManager(TenantScopedManagerMixin, ModelManager):
    queryset_class = ModelQuerySet


class TenantUnscopedManager(UnscopedManager):
    def get_queryset(self):
        return ModelQuerySet(self.model, using=self._db)


class TenantModel(TenantScopedModel, ModelMixin):
    objects = TenantModelManager()
    unscoped = TenantUnscopedManager()

    class Meta:
        abstract = True
        ordering = ["-id"]
        base_manager_name = "unscoped"


class TenantNameModel(TenantModel):
    name = models.CharField(max_length=255)

    class Meta(TenantModel.Meta):
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name[:60]


class TenantNumberedModel(TenantModel):
    """Adds a per-tenant human-facing number such as J-0042.

    Subclasses set ``number_prefix`` (the default shown to people) and
    ``number_setting`` (the key under the Blueprint's ``settings.numbering``,
    so a business can use its own prefixes, for example "WO" instead of "J").
    ``number_sequence`` is the counter key (defaults to the model label).
    """

    number = models.CharField(max_length=32, blank=True, default="", db_index=True)

    number_prefix: str = ""
    number_setting: str = ""
    number_sequence: str = ""
    number_width: int = 4

    class Meta(TenantModel.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"], name="%(app_label)s_%(class)s_unique_number_per_tenant"
            )
        ]

    def save(self, *args, **kwargs):
        if not self.number:
            key = self.number_sequence or self._meta.label_lower
            tenant = self.tenant if self.tenant_id else None
            self.number = next_number(key, prefix=self._number_prefix(tenant), width=self.number_width, tenant=tenant)
        return super().save(*args, **kwargs)

    def _number_prefix(self, tenant) -> str:
        if not self.number_setting:
            return self.number_prefix
        from blueprint.config import get_effective_config
        from tenancy.context import require_current_tenant

        config = get_effective_config(tenant or require_current_tenant())
        return str((config.settings.get("numbering") or {}).get(self.number_setting) or self.number_prefix)
