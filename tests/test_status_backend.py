from django.contrib.auth.backends import ModelBackend
from django.test import SimpleTestCase

from django_jt.backends.authentication import StatusBackend


class StatusBackendTests(SimpleTestCase):
    def test_is_model_backend_subclass(self):
        self.assertTrue(issubclass(StatusBackend, ModelBackend))
