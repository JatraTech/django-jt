import warnings
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from rest_framework import serializers

from django_jt.mixins.views import BaseModelViewSet


class _DummySerializer(serializers.Serializer):
    pass


class _LegacyViewSet(BaseModelViewSet):
    serializer_class = _DummySerializer
    serializers = {}
    action_serializers = {"custom": _DummySerializer}


class BaseModelViewSetActionSerializersTests(SimpleTestCase):
    def test_action_serializers_deprecated_fallback(self) -> None:
        view = _LegacyViewSet()
        view.action = "custom"
        view.request = MagicMock()
        view.request.version = None

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            resolved = view.get_serializer_class()

        self.assertIs(resolved, _DummySerializer)
        self.assertTrue(any("action_serializers" in str(w.message) for w in caught))
