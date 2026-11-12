from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.db import connection
from django.utils import timezone

from django_jt.ordering import ProximityOrderingFilter
from tests.models import TimedItem


class _OrderingView:
    ordering_fields = ["due_at", "name"]


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="Proximity ordering uses Extract(..., 'epoch')")
def test_proximity_ordering_closest_due_at_first():
    now = timezone.now()
    TimedItem.objects.create(name="far", due_at=now + timedelta(days=10))
    near = TimedItem.objects.create(name="near", due_at=now + timedelta(hours=1))
    TimedItem.objects.create(name="past", due_at=now - timedelta(hours=1))

    request = MagicMock()
    request.query_params = {"ordering": "=due_at"}

    backend = ProximityOrderingFilter()
    qs = backend.filter_queryset(request, TimedItem.objects.all(), _OrderingView())
    assert list(qs.values_list("pk", flat=True))[0] == near.pk


def test_proximity_remove_invalid_fields():
    backend = ProximityOrderingFilter()
    view = _OrderingView()
    request = MagicMock()
    qs = TimedItem.objects.all()
    cleaned = backend.remove_invalid_fields(qs, ["=due_at", "-invalid"], view, request)
    assert cleaned == ["=due_at"]
