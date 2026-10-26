import operator
from functools import reduce
from typing import ClassVar

from django.db.models import Q
from django_filters import rest_framework as dj_filters
from rest_framework.filters import SearchFilter as SearchFilter_

from django_jt.mixins.models import NameModelMixin


class BaseModelFilterSet(dj_filters.FilterSet):
    """What every list gets on top of its own filters: ``?created_at_after=`` / ``?created_at_before=``.

    Not meant to be a view's ``filterset_class`` by itself (it has no model): :class:`FilterBackend`
    builds each view's FilterSet on top of it from ``filterset_fields``.
    """

    created_at = dj_filters.DateFromToRangeFilter()

    class Meta:
        abstract = True


def _model_has_field(model, name: str) -> bool:
    from django.core.exceptions import FieldDoesNotExist

    try:
        model._meta.get_field(name)
    except FieldDoesNotExist:
        return False
    return True


class FilterBackend(dj_filters.DjangoFilterBackend):
    """django-filter's backend, made to honor ``filterset_fields`` on every view.

    * no ``filterset_class`` (or the bare ``BaseModelFilterSet``): a FilterSet for the view's model built
      on :class:`BaseModelFilterSet` with ``filterset_fields`` (plus ``created_at`` ranges when the model
      has that field);
    * an explicit ``filterset_class`` and ``filterset_fields`` too: the explicit class, extended with any
      listed field it doesn't already filter on (its own declared filters win);
    * an explicit ``filterset_class`` alone: used as is.
    """

    filterset_base = BaseModelFilterSet

    def get_filterset_class(self, view, queryset=None):
        filterset_class = getattr(view, "filterset_class", None)
        if filterset_class is BaseModelFilterSet:
            filterset_class = None
        fields = getattr(view, "filterset_fields", None) or []
        if not isinstance(fields, dict):
            fields = list(fields)

        if filterset_class is not None:
            missing = [f for f in fields if f not in filterset_class.base_filters]
            if not missing or queryset is None:
                return super().get_filterset_class(view, queryset)
            own_meta = getattr(filterset_class, "Meta", object)
            own_fields = getattr(own_meta, "fields", None) or []
            if isinstance(own_fields, str):
                return super().get_filterset_class(view, queryset)
            if isinstance(own_fields, dict) or isinstance(fields, dict):
                merged = (
                    {name: ["exact"] for name in own_fields}
                    if not isinstance(own_fields, dict)
                    else {}
                )
                merged.update(own_fields if isinstance(own_fields, dict) else {})
                merged.update(
                    {
                        name: (fields[name] if isinstance(fields, dict) else ["exact"])
                        for name in missing
                    }
                )
            else:
                merged = list(own_fields) + [f for f in missing if f not in own_fields]
            model = filterset_class._meta.model or queryset.model
            meta = type("Meta", (own_meta,), {"model": model, "fields": merged})
            return type(
                f"{filterset_class.__name__}WithFields",
                (filterset_class,),
                {"Meta": meta},
            )

        if queryset is None:
            return None
        model = queryset.model
        has_created_at = _model_has_field(model, "created_at")
        if not fields and not has_created_at:
            return None
        attrs: dict = {}
        if not has_created_at:
            attrs["created_at"] = None
        attrs["Meta"] = type(
            "Meta", (self.filterset_base.Meta,), {"model": model, "fields": fields}
        )
        return type(f"{model.__name__}AutoFilterSet", (self.filterset_base,), attrs)


class SearchFilter(SearchFilter_):
    def get_search_fields(self, view, request):
        fields = super().get_search_fields(view, request) or list()
        fields.append("id")
        fields = set(fields)
        if (
            (serializer := getattr(view, "serializer_class", None))
            and hasattr(serializer, "Meta")
            and hasattr(serializer.Meta, "model")
            and issubclass(serializer.Meta.model, NameModelMixin)
        ):
            fields = fields.union(["name"])
        if field_from_querystring := request.query_params.get("search_fields"):
            fields = fields.union(
                [
                    search_field.strip()
                    for search_field in field_from_querystring.split(",")
                ]
            )
        return fields


class ExtendedSearchFilter(SearchFilter):
    """
    Custom SearchFilter that applies default DRF search_fields filtering,
    then ORs additional conditions for selected fields.
    """

    extra_search_fields: ClassVar[list[str]] = []

    def filter_queryset(self, request, queryset, view):
        queryset = super().filter_queryset(request, queryset, view)

        search_terms = self.get_search_terms(request)
        extra_fields = getattr(view, "extra_search_fields", self.extra_search_fields)

        if not search_terms or not extra_fields:
            return queryset

        or_filter = reduce(
            operator.or_,
            (
                reduce(
                    operator.or_,
                    (Q(**{f"{field}__icontains": term}) for field in extra_fields),
                )
                for term in search_terms
            ),
        )

        return (queryset | view.get_queryset().filter(or_filter)).distinct()
