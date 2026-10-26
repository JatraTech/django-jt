import io
import json
from datetime import datetime
from typing import Literal, Protocol

import polars as pl
from django.db.models import Q, QuerySet
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import decorators, generics, response, viewsets
from styleframe import StyleFrame

from app.utils import get_last_date_of_week
from app.utils.pagination import StandardPagination
from app.utils.validators import AnalyticsData
from user.constants import UserRoleChoices
from user.models import User


class AudienceFilterFn(Protocol):
    """
    A callable used to filter querysets based on a user.

    Parameters
    ----------
    user : User
        The user instance used to build the filter condition.

    Returns
    -------
    Q
        A `django.db.models.Q` object representing the filter to apply.
    """

    def __call__(self, user: User) -> Q: ...


class BaseListView(generics.ListAPIView):
    ordering = ["-id"]
    pagination_class = StandardPagination
    # None on purpose: app.utils.filters.FilterBackend builds each list's FilterSet from ``filterset_fields``
    # on top of BaseModelFilterSet. Setting a class here made django-filter ignore every ``filterset_fields``.
    filterset_class = None
    audience_lookups: dict[UserRoleChoices, AudienceFilterFn | str] = {}
    ordering_fields = "__all__"
    ordering_field_map = {}
    extra_search_fields = []


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="extend_fields",
            type=str,
            many=True,
        )
    ]
)
class BaseModelViewSet(
    BaseListView,
    viewsets.ModelViewSet,
):
    serializers = {}

    def get_serializer_class(self):
        action = self.action
        version = getattr(self.request, "version", None)

        if version:
            return self.serializers.get(
                f"{action}_{version}",
                self.serializers.get(action, self.serializer_class),
            )

        return self.serializers.get(action, self.serializer_class)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if extendable_fields := self.request.query_params.get(
            "extend_fields",
            "",
        ):
            context["extendable_fields"] = extendable_fields.split(",")
        return context


class AnalyticsDataViewMixin(generics.ListAPIView):
    analytics_data: AnalyticsData

    def get_aggregation_queryset(self):
        return self.filter_queryset(self.get_queryset())

    def list(self, request, *args, **kwargs):
        qs = self.get_aggregation_queryset()
        analytics_data = self.analytics_data
        for item in analytics_data:
            if item.key in qs:
                item.value = qs[item.key]
        return response.Response(json.loads(analytics_data.model_dump_json()))


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="interval_type",
            description="Type of interval for the graph data",
            required=False,
            type=OpenApiTypes.STR,
            enum=["weekly", "monthly", "yearly"],
        ),
    ],
)
class AnalyticsGraphViewMixin(generics.ListAPIView):
    interval_type_annotations = {
        "weekly": "created_at__week",
        "monthly": "created_at__month",
        "yearly": "created_at__year",
    }
    interval_type: Literal["weekly", "monthly", "yearly"]

    def get_queryset(self):
        """Must return: data, interval_data, year"""
        raise NotImplementedError

    def map_weekly_data(self, item):
        item["label_x"] = get_last_date_of_week(year=item.get("year"), week=item.get("interval_data")).strftime(
            "%Y-%m-%d"
        )
        item["label_y"] = f"${item.get('data')}"
        return item

    def map_monthly_data(self, item):
        month = item.get("interval_data")
        year = item.get("year")
        date_obj = datetime(year, month, 1)

        item["label_x"] = f"{date_obj.strftime('%b, %Y')}"
        item["label_y"] = f"${item.get('data')}"
        return item

    def map_yearly_data(self, item):
        item["label_x"] = f"{item.get('interval_data')}"
        item["label_y"] = f"${item.get('data')}"
        return item

    def get_graph_data(self, qs: QuerySet, interval_type: Literal["weekly", "monthly", "yearly"]):
        data = []
        if interval_type == "weekly":
            data = map(lambda x: self.map_weekly_data(x), qs)
        elif interval_type == "monthly":
            data = map(lambda x: self.map_monthly_data(x), qs)
        elif interval_type == "yearly":
            data = map(lambda x: self.map_yearly_data(x), qs)
        return list(data)

    def list(self, request, *args, **kwargs):
        interval_type = request.query_params.get("interval_type", "monthly")
        self.interval_type = interval_type
        data = self.get_graph_data(
            self.filter_queryset(self.get_queryset()),
            interval_type,
        )
        return response.Response(data)


class NestedViewSetMixin(BaseModelViewSet):
    parent_lookup_kwargs = {}  # key: lookup from url, value: field to lookup. i.e. unit_pk: unit

    def get_parent_lookup_filters(self):
        filters = {}
        kwargs = self.kwargs
        for k, v in self.parent_lookup_kwargs.items():
            if k in kwargs:
                filters[v] = kwargs[k]
        return filters

    def get_queryset(self):
        return super().get_queryset().filter(**self.get_parent_lookup_filters())


class ExportMixin:
    def __init__(self, url_path="export", queryset=None) -> None:
        self.url_path = url_path
        self.custom_queryset = queryset

    def get_export_file_name(self):
        now = timezone.now()
        try:
            filename = f"""{self.__class__.__name__.replace("ViewSet", "")}"""
        except Exception:
            filename = "file"
        return f"""{filename} {now.strftime("%m-%d-%Y")}"""

    @decorators.action(detail=False, methods=["get"], url_path="export/xlsx")
    def export_xlsx(
        self,
        request,
        queryset: QuerySet | None = None,
        columns: list | None = None,
        rename_columns: dict | None = None,
        ordered_column=None,
        exclude_columns=None,
        change_types=None,
        format_types=None,
        *args,
        **kwargs,
    ):
        queryset = queryset if queryset else self.filter_queryset(self.get_queryset())
        data = list(queryset.values(*(columns or [])))
        rename_columns = rename_columns or {}
        ordered_column = ordered_column or []
        exclude_columns = exclude_columns or []
        change_types = change_types or {}
        format_types = format_types or []

        if not data:
            return HttpResponse("No data to export", status=204)
        df = pl.DataFrame(data)

        if ordered_column:
            cols = [c for c in ordered_column if c in df.columns] + [c for c in df.columns if c not in ordered_column]
            df = df.select(cols)

        for col, dtype in change_types.items():
            if col in df.columns:
                try:
                    df = df.with_columns(df[col].cast(dtype).alias(col))
                except Exception:
                    pass

        if format_types:
            for f in format_types:
                if callable(f):
                    for col in df.columns:
                        df = df.with_columns(df[col].map_elements(lambda v, f=f, col=col: f(col, v)).alias(col))

        df = df.rename(rename_columns)
        df = df.drop([c for c in exclude_columns if c in df.columns])

        # convert datetimetime cols to str
        for col, dtype in zip(df.columns, df.dtypes, strict=True):
            if dtype == pl.Datetime or dtype == pl.Date:
                df = df.with_columns(df[col].dt.strftime("%Y-%m-%dT%H:%M:%S").alias(col))

        bytes_io = io.BytesIO()
        sf = StyleFrame(df.to_dicts())

        with StyleFrame.ExcelWriter(bytes_io) as writer:
            sf.to_excel(writer, best_fit=list(df.columns))
        filename = f"{self.get_export_file_name()}.xlsx"
        response = HttpResponse(
            bytes_io.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
