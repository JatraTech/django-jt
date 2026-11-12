from unittest.mock import MagicMock

import pytest

from django_jt.mixins.export import ExportMixin, _require_export_deps
from tests.models import Item


@pytest.mark.django_db
def test_export_xlsx_empty_queryset_returns_204():
    _require_export_deps()

    class ViewSet(ExportMixin):
        def filter_queryset(self, queryset):
            return queryset

        def get_queryset(self):
            return Item.objects.none()

    view = ViewSet()
    response = view.export_xlsx(MagicMock())
    assert response.status_code == 204


@pytest.mark.django_db
def test_export_xlsx_with_rows_returns_xlsx():
    _require_export_deps()
    Item.objects.create(name="One")

    class ViewSet(ExportMixin):
        def filter_queryset(self, queryset):
            return queryset

        def get_queryset(self):
            return Item.objects.all()

    view = ViewSet()
    response = view.export_xlsx(
        MagicMock(),
        columns=["name"],
    )
    assert response.status_code == 200
    assert (
        response["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(response.content) > 100
