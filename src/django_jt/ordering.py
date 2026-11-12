from django.db.models import (
    DateField,
    DateTimeField,
    DurationField,
    ExpressionWrapper,
    F,
)
from django.db.models.functions import Abs, Extract, Now
from rest_framework.filters import OrderingFilter


class CustomOrderingFilter(OrderingFilter):
    """
    Extended OrderingFilter that supports alias ordering via `ordering_field_map`.
    Accepts both real and alias fields.
    Example:
    ordering_field_map = {
        "name": "first_name",
        "email": "email",
    }
    Then you can order by name or email.
    """

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid_fields = [item[0] for item in self.get_valid_fields(queryset, view, {"request": request})]
        alias_map = getattr(view, "ordering_field_map", {}) or {}
        cleaned_fields = []

        for term in fields:
            is_desc = term.startswith("-")
            raw_field = term[1:] if is_desc else term
            actual_field = alias_map.get(raw_field, raw_field)
            if actual_field in valid_fields:
                cleaned_fields.append(f"-{actual_field}" if is_desc else actual_field)
        return cleaned_fields


class ProximityOrderingFilter(OrderingFilter):
    """
    OrderingFilter with nulls-last behavior and ``=`` prefix for date proximity.

    Use ``?ordering==due_at`` (leading ``=``) on a ``DateField``/``DateTimeField`` to sort
    by absolute seconds from now. Other terms use ascending/descending with nulls last.

    Proximity sorting uses ``Extract(..., 'epoch')`` and is **PostgreSQL-oriented**.
    """

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid_fields = [item[0] for item in self.get_valid_fields(queryset, view, {"request": request})]

        def term_valid(term):
            if term.startswith("-") or term.startswith("="):
                term = term[1:]
            return term in valid_fields

        return [term for term in fields if term_valid(term)]

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset

        fields = []
        for field in ordering:
            if field.startswith("="):
                field_name = field[1:]
                if field_name.startswith("-"):
                    field_name = field_name[1:]

                model_field = queryset.model._meta.get_field(field_name)
                if isinstance(model_field, (DateField, DateTimeField)):
                    time_from_now = ExpressionWrapper(F(field_name) - Now(), output_field=DurationField())
                    queryset = queryset.annotate(
                        _time_from_now=time_from_now,
                        _seconds_from_now=Abs(Extract(time_from_now, "epoch")),
                    )
                    fields.append(F("_seconds_from_now").asc(nulls_last=True))
                    continue

            if field.startswith("-"):
                fields.append(F(field[1:]).desc(nulls_last=True))
            else:
                fields.append(F(field).asc(nulls_last=True))

        return queryset.order_by(*fields)
