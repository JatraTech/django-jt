from rest_framework import generics, viewsets

from django_jt.pagination import StandardPagination

try:
    from drf_spectacular.utils import OpenApiParameter, extend_schema
except ImportError:
    OpenApiParameter = None

    def extend_schema(*args, **kwargs):
        def decorator(cls):
            return cls

        return decorator


class BaseListView(generics.ListAPIView):
    ordering = ["-id"]
    pagination_class = StandardPagination
    # None on purpose: django_jt.filters.FilterBackend builds each list's FilterSet from
    # ``filterset_fields`` on top of BaseModelFilterSet.
    filterset_class = None
    audience_lookups: dict = {}
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
    if OpenApiParameter is not None
    else []
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


class NestedViewSetMixin(BaseModelViewSet):
    parent_lookup_kwargs = {}

    def get_parent_lookup_filters(self):
        filters = {}
        kwargs = self.kwargs
        for k, v in self.parent_lookup_kwargs.items():
            if k in kwargs:
                filters[v] = kwargs[k]
        return filters

    def get_queryset(self):
        return super().get_queryset().filter(**self.get_parent_lookup_filters())
