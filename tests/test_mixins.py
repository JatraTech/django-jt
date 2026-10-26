import pytest

from tests.models import Item


@pytest.mark.django_db
def test_name_model_mixin_create_and_active():
    item = Item.objects.create(name="Widget")
    assert item.name == "Widget"
    assert item.is_active is True
    assert Item.objects.all_active().filter(pk=item.pk).exists()

    item.is_active = False
    item.save()
    assert Item.objects.all_inactive().filter(pk=item.pk).exists()
    assert not Item.objects.all_active().filter(pk=item.pk).exists()
