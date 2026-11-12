import pytest
from django.contrib.contenttypes.models import ContentType

from django_jt.mixins.serializers import ContentTypeByNameSerializer


@pytest.mark.django_db
def test_content_type_by_name_round_trip():
    ct = ContentType.objects.get_for_model(ContentType)
    field = ContentTypeByNameSerializer()
    label = field.to_representation(ct)
    assert label == "contenttypes.contenttype"
    assert field.to_internal_value(label) == ct
