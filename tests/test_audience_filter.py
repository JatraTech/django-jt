from unittest.mock import MagicMock

import pytest
from django.db.models import Q

from django_jt.filters import AudienceFilter
from tests.models import Item, User


class _StubView:
    authentication_classes = [object]


@pytest.mark.django_db
def test_audience_filter_skips_when_no_auth_classes():
    backend = AudienceFilter()
    view = _StubView()
    view.authentication_classes = []
    qs = Item.objects.all()
    request = MagicMock()
    assert backend.filter_queryset(request, qs, view) is qs


@pytest.mark.django_db
def test_audience_filter_callable_lookup():
    owner = User.objects.create_user(username="owner", password="x")
    other = User.objects.create_user(username="other", password="x")
    owner.user_role = "member"
    other.user_role = "member"

    mine = Item.objects.create(name="mine")
    mine.created_by = owner
    mine.save()
    theirs = Item.objects.create(name="theirs")
    theirs.created_by = other
    theirs.save()

    class View(_StubView):
        audience_lookups = {"member": lambda u: Q(created_by=u)}

    backend = AudienceFilter()
    request = MagicMock()
    request.user = owner

    filtered = backend.filter_queryset(request, Item.objects.all(), View())
    assert list(filtered.values_list("name", flat=True)) == ["mine"]


@pytest.mark.django_db
def test_audience_filter_kwarg_lookup():
    user = User.objects.create_user(username="u", password="x")
    user.user_role = "member"

    item = Item.objects.create(name="a")
    item.created_by = user
    item.save()
    Item.objects.create(name="b")

    class View(_StubView):
        audience_lookups = {"member": "created_by"}

    backend = AudienceFilter()
    request = MagicMock()
    request.user = user

    filtered = backend.filter_queryset(request, Item.objects.all(), View())
    assert filtered.count() == 1
    assert filtered.get().name == "a"
