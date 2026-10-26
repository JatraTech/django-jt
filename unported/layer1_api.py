"""
Small builder for the Layer 1 record endpoints (direction ``11`` L1.x): a serializer and a tenant viewset
per model, with the platform's permissions (``module`` capabilities), audit of writes and tenant scoping
(``TenantModelViewSet``). Each app declares its own in ``<app>/views/layer1.py``; workflow actions
(close a loop, confirm a deadline, invoice a receivable) are explicit ``@action``s there, calling services.

    LoopViewSet = record_viewset(OpenLoop, module="work", read_only=("status", "chase_count"), ordering=["-id"])
"""

from __future__ import annotations

from app.utils.mixins.serializers import BaseModelSerializer
from app.utils.mixins.tenant_views import TenantModelViewSet

#: Fields a client never writes on any Layer 1 record.
SERVER_FIELDS = ("id", "tenant")


def record_serializer(model, *, fields="__all__", read_only=(), exclude=()):
    meta_attrs = {"model": model, "read_only_fields": tuple(read_only) + SERVER_FIELDS}
    if exclude:
        meta_attrs["exclude"] = tuple(exclude) + ("tenant",)
    else:
        meta_attrs["fields"] = fields
    if fields == "__all__" and not exclude:
        meta_attrs.pop("fields")
        meta_attrs["exclude"] = ("tenant",)
    meta = type("Meta", (), meta_attrs)
    return type(f"{model.__name__}Serializer", (BaseModelSerializer,), {"Meta": meta})


def record_viewset(
    model,
    *,
    module: str,
    serializer=None,
    ordering=("-id",),
    filterset_fields=(),
    read_only=(),
    exclude=(),
    http_method_names=None,
    extra=None,
):
    attrs = {
        "queryset": model.unscoped.all(),
        "serializer_class": serializer or record_serializer(model, read_only=read_only, exclude=exclude),
        "module": module,
        "ordering": list(ordering),
        "filterset_fields": list(filterset_fields),
    }
    if http_method_names:
        attrs["http_method_names"] = http_method_names
    attrs.update(extra or {})
    return type(f"{model.__name__}ViewSet", (TenantModelViewSet,), attrs)
