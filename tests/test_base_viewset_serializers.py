import warnings
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from rest_framework import serializers

from django_jt.mixins.views import BaseModelViewSet


class _DummySerializer(serializers.Serializer):
    pass


class _OtherSerializer(serializers.Serializer):
    pass


class _ActionSerializersViewSet(BaseModelViewSet):
    serializer_class = _DummySerializer
    action_serializers = {"custom": _OtherSerializer}


class _LegacySerializersAttrViewSet(BaseModelViewSet):
    serializer_class = _DummySerializer
    serializers = {"custom": _OtherSerializer}


class BaseModelViewSetActionSerializersTests(SimpleTestCase):
    def test_action_serializers_resolves_per_action(self) -> None:
        view = _ActionSerializersViewSet()
        view.action = "custom"
        view.request = MagicMock()
        view.request.version = None

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            resolved = view.get_serializer_class()

        self.assertIs(resolved, _OtherSerializer)
        self.assertFalse(caught)

    def test_legacy_serializers_attr_is_ignored(self) -> None:
        view = _LegacySerializersAttrViewSet()
        view.action = "custom"
        view.request = MagicMock()
        view.request.version = None

        self.assertIs(view.get_serializer_class(), _DummySerializer)
