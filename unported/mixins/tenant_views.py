"""
Base viewsets for tenant data. Every module's viewsets extend these.

    class AccountViewSet(TenantModelViewSet):
        queryset = Account.unscoped.select_related("primary_contact")   # unscoped at class level!
        serializer_class = AccountSerializer
        module = "crm"                                                  # access-control module key

Why ``unscoped`` at class level: the class body runs at import time, when no
tenant is current, so ``Account.objects`` would bake in an empty result. This
base class re-applies the tenant filter on every request, and Postgres
row-level security applies regardless.

What you get:
  * IsAuthenticated + IsTenantMember + module permission (role x action) checks,
  * querysets filtered to the request's tenant,
  * the template's serializer-per-action, filtering, search, ordering, pagination,
  * in a regulated business, a view log of every record whose protected pack fields a response showed
    (lists and custom actions included; ``reads_audited``).
"""

from __future__ import annotations

import datetime
import io
from decimal import Decimal

import openpyxl
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import decorators
from rest_framework.exceptions import NotFound
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from app.utils.mixins.views import BaseListView, BaseModelViewSet
from tenancy.context import require_current_tenant
from tenancy.permissions import IsTenantMember


def _module_permission_class():
    # Imported lazily: the access app depends on this module's callers, not vice versa.
    from access.permissions import HasModulePermission

    return HasModulePermission


def reads_audited(view, request) -> bool:
    """Whether reads through ``view`` go to the audit trail: the view's ``audit_reads`` when it sets one,
    otherwise only in a regulated business (``Tenant.data_protection`` or a regulated pack)."""
    flag = getattr(view, "audit_reads", None)
    if flag is not None:
        return bool(flag)
    membership = getattr(request, "membership", None)
    if membership is not None and getattr(membership, "kind", "") == "partner":
        return True  # A4: every record a bookkeeper partner opens is in the client's trail
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return False
    if tenant.is_regulated:
        return True
    from access.services import is_regulated

    return is_regulated(tenant)


def audit_protected_reads(view, request, seen: dict, *, skip=()) -> int:
    """One audit entry per record whose protected pack fields went out (``blueprint.fields``): ``view``
    for a detail, ``list`` otherwise. The field names are kept (``meta.fields``), never the values."""
    from audit.services import describe, record_many
    from audit.summaries import record_params

    detail = getattr(view, "action", None) == "retrieve"
    verb, code = ("Viewed", "record.view") if detail else ("Listed", "record.list")
    within = getattr(view, "_audited_view_ref", None)
    entries = []
    for key, (instance, keys) in seen.items():
        if key in skip:
            continue
        meta = {"fields": sorted(keys)}
        if within and detail:
            meta["within"] = within
        entries.append(
            {
                "subject": instance,
                "summary": f"{verb} {describe(instance)}",
                "summary_code": code,
                "summary_params": record_params(instance),
                "meta": meta,
            }
        )
    return record_many("view" if detail else "list", entries, request=request)


class TenantViewMixin:
    #: Access-control module key, for example "crm". Required.
    module: str = ""
    tenancy_scope = "tenant"
    # Declared so the tenancy.E004 startup check can see it; get_permissions() is authoritative.
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get_permissions(self):
        perms = [IsAuthenticated(), IsTenantMember()]
        if self.module:
            perms.append(_module_permission_class()())
        perms.extend(p() for p in getattr(self, "extra_permission_classes", ()))
        return perms

    # The view log of protected fields (SEC-04): every record whose protected pack fields a successful
    # read shows is collected while the request runs and written to the audit trail at the end.
    def dispatch(self, request, *args, **kwargs):
        from blueprint.fields import collecting_protected_reads

        with collecting_protected_reads() as seen:
            self._protected_reads_seen = seen
            return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)  # type: ignore[misc]
        seen = getattr(self, "_protected_reads_seen", None)
        if seen and request.method in SAFE_METHODS and response.status_code < 400 and reads_audited(self, request):
            audit_protected_reads(self, request, seen, skip={getattr(self, "_audited_view_key", None)})
            seen.clear()
        return response

    def get_queryset(self):
        qs = super().get_queryset()  # type: ignore[misc]
        if qs.query.is_empty():
            raise ImproperlyConfigured(
                f"{type(self).__name__}.queryset was built from `objects` at import time and is always "
                "empty. Build the class-level queryset from `Model.unscoped`."
            )
        qs = qs.filter(tenant_id=require_current_tenant().pk)
        if getattr(self.request, "access_scope", "all") == "own":
            qs = self.filter_own(qs, getattr(self.request, "membership", None))
        return qs

    # "Own records" for roles granted ``capability:own``. Override per viewset
    # (for example: appointments assigned to my resource, accounts I manage).
    def filter_own(self, queryset, membership):
        if membership is None:
            return queryset.none()
        return queryset.filter(created_by_id=membership.user_id)

    def is_own(self, obj, membership) -> bool:
        return getattr(obj, "created_by_id", None) == membership.user_id


def _excel_cell(value):
    """Spreadsheet-safe value: dates as ISO text, decimals as text, and no formula injection."""
    if isinstance(value, datetime.datetime):
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M") if timezone.is_aware(value) else value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dict, list)):
        return str(value)
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


class AuditedWritesMixin:
    """Record creates, updates, deletes (and reads, when asked) in the audit trail.

    ``audit_reads``: None = record reads only for regulated businesses;
    True = always; False = never.
    """

    audit_reads: bool | None = None

    def _audit(self, action, obj, **kwargs):
        from audit.services import describe, record
        from audit.summaries import record_params

        verb = {"create": "Created", "update": "Updated", "delete": "Deleted", "view": "Viewed"}[action]
        kwargs.setdefault("summary_code", f"record.{action}")
        kwargs.setdefault("summary_params", record_params(obj))
        record(action, subject=obj, request=self.request, summary=f"{verb} {describe(obj)}", **kwargs)

    def _should_audit_reads(self) -> bool:
        return reads_audited(self, self.request)

    def perform_create(self, serializer):
        super().perform_create(serializer)  # type: ignore[misc]
        self._audit("create", serializer.instance)

    def perform_update(self, serializer):
        from audit.services import changed_field_names

        changed = changed_field_names(serializer.instance, serializer.validated_data)
        super().perform_update(serializer)  # type: ignore[misc]
        if changed:
            self._audit("update", serializer.instance, changed_fields=changed)

    def perform_destroy(self, instance):
        self._audit("delete", instance)
        super().perform_destroy(instance)  # type: ignore[misc]

    #: Columns for the audited Excel export (``queryset.values(*export_columns)``). Empty = no export.
    #: Explicit on purpose: encrypted pack fields and secrets must never land in a spreadsheet.
    export_columns: list[str] = []

    @decorators.action(detail=False, methods=["get"], url_path="export/xlsx")
    def export_xlsx(self, request, *args, **kwargs):
        from audit.services import record

        if not self.export_columns:
            raise NotFound("This list can't be exported.")
        queryset = self.filter_queryset(self.get_queryset())  # type: ignore[attr-defined]
        rows = list(queryset.values(*self.export_columns))
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(list(self.export_columns))
        for row in rows:
            sheet.append([_excel_cell(row[c]) for c in self.export_columns])
        buffer = io.BytesIO()
        workbook.save(buffer)
        model = queryset.model
        record(
            "export",
            request=request,
            summary=f"Exported {len(rows)} {model._meta.verbose_name_plural}",
            summary_code="records.export",
            summary_params={"count": len(rows), "kind": model._meta.label_lower},
            meta={"format": "xlsx", "rows": len(rows), "query": request.GET.urlencode()[:200]},
        )
        name = f"{model._meta.verbose_name_plural.title()} {timezone.localdate():%Y-%m-%d}.xlsx"
        resp = HttpResponse(
            buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp["Content-Disposition"] = f'attachment; filename="{name}"'
        return resp

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()  # type: ignore[attr-defined]
        data = self.get_serializer(instance).data  # type: ignore[attr-defined]
        if self._should_audit_reads():
            self._audit("view", instance)
            # Its own protected fields are covered by this entry; records shown inside it get their own.
            self._audited_view_key = (instance._meta.label_lower, instance.pk)
            self._audited_view_ref = f"{instance._meta.label_lower}:{instance.pk}"
        return Response(data)


class TenantModelViewSet(TenantViewMixin, AuditedWritesMixin, BaseModelViewSet):
    # Declared so the tenancy.E004 startup check can see it; get_permissions() is authoritative.
    permission_classes = [IsAuthenticated, IsTenantMember]


class TenantListView(TenantViewMixin, BaseListView):
    permission_classes = [IsAuthenticated, IsTenantMember]
