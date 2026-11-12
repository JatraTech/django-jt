from django.test import TestCase, override_settings


class Auth901OidcEnabledTests(TestCase):
    @override_settings(AUTH901_CLIENT_ID="")
    def test_disabled_when_client_id_absent(self):
        from unittest.mock import patch

        from django_jt.auth.defaults import auth901_oidc_enabled

        with patch("django_jt.auth.defaults._setting", return_value=""):
            self.assertFalse(auth901_oidc_enabled())

    @override_settings(AUTH901_CLIENT_ID="test-client")
    def test_enabled_when_client_and_mozilla_present(self):
        from django_jt.auth.defaults import auth901_oidc_enabled

        self.assertTrue(auth901_oidc_enabled())
