from collections import OrderedDict

from rest_framework import response
from rest_framework.pagination import PageNumberPagination

#: The largest page any list endpoint answers (``?page_size=`` above it gets this many).
MAX_PAGE_SIZE = 200


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE


class DummyPagination(PageNumberPagination):
    """Returns the full queryset without slicing; kept for callers that disable paging."""

    def paginate_queryset(self, queryset, request, view=None):
        return queryset

    def get_paginated_response(self, data):
        return response.Response(
            OrderedDict(
                [
                    ("count", len(data)),
                    ("next", None),
                    ("previous", None),
                    ("results", data),
                ]
            )
        )
