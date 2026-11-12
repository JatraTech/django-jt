from django_jt.pagination import (
    StandardCursorPagination,
    StandardLimitOffsetPagination,
)


def test_limit_offset_defaults():
    paginator = StandardLimitOffsetPagination()
    assert paginator.default_limit == 20


def test_cursor_pagination_defaults():
    paginator = StandardCursorPagination()
    assert paginator.page_size == 20
    assert paginator.ordering == "name"
