import json
from datetime import datetime
from typing import Literal

from django.db.models import QuerySet
from rest_framework import generics, response

from django_jt import get_last_date_of_week
from django_jt.analytics.validators import AnalyticsData

try:
    from drf_spectacular.types import OpenApiTypes
    from drf_spectacular.utils import OpenApiParameter, extend_schema
except ImportError:
    OpenApiTypes = None
    OpenApiParameter = None

    def extend_schema(*args, **kwargs):
        def decorator(cls):
            return cls

        return decorator


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


_GRAPH_SCHEMA_PARAMS = (
    [
        OpenApiParameter(
            name="interval_type",
            description="Type of interval for the graph data",
            required=False,
            type=OpenApiTypes.STR,
            enum=["weekly", "monthly", "yearly"],
        ),
    ]
    if OpenApiParameter is not None and OpenApiTypes is not None
    else []
)


@extend_schema(parameters=_GRAPH_SCHEMA_PARAMS)
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
        item["label_x"] = get_last_date_of_week(
            year=item.get("year"), week=item.get("interval_data")
        ).strftime("%Y-%m-%d")
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

    def get_graph_data(
        self, qs: QuerySet, interval_type: Literal["weekly", "monthly", "yearly"]
    ):
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
