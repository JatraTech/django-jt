from pathlib import Path
from unittest.mock import patch

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from django_jt.backends.email.graph import (
    GraphAuthError,
    GraphConfigurationError,
    GraphEmailBackend,
    GraphSendError,
    _GraphMailClient,
    graph_is_configured,
)


class GraphBackendConstantsTests(SimpleTestCase):
    def test_scopes_and_token_cache_path(self):
        self.assertEqual(GraphEmailBackend.SCOPES, ["Mail.Send"])
        self.assertEqual(GraphEmailBackend.TOKEN_CACHE_PATH, ".secrets/ms_graph_msal_cache.json")


@override_settings(
    MS_GRAPH_CLIENT_ID="client-id",
    MS_GRAPH_TENANT_ID="tenant-id",
)
class GraphMailClientTests(SimpleTestCase):
    @patch.object(GraphEmailBackend, "get_token_cache_path")
    def test_graph_is_configured_when_cache_exists(self, mock_cache_path):
        mock_cache_path.return_value = Path("/tmp/ms_graph_msal_cache.json")
        with patch.object(Path, "exists", return_value=True):
            self.assertTrue(graph_is_configured())

    @patch.object(GraphEmailBackend, "get_token_cache_path")
    def test_graph_is_not_configured_without_cache(self, mock_cache_path):
        mock_cache_path.return_value = Path("/tmp/ms_graph_msal_cache.json")
        with patch.object(Path, "exists", return_value=False):
            self.assertFalse(graph_is_configured())

    @override_settings(MS_GRAPH_CLIENT_ID="")
    def test_client_requires_configuration(self):
        with self.assertRaises(GraphConfigurationError):
            _GraphMailClient()

    @patch("django_jt.backends.email.graph.requests.post")
    @patch("django_jt.backends.email.graph.msal.PublicClientApplication")
    def test_send_posts_html_payload(self, mock_app_cls, mock_post):
        mock_app = mock_app_cls.return_value
        mock_app.get_accounts.return_value = [{"username": "andy@new901.io"}]
        mock_app.acquire_token_silent.return_value = {"access_token": "token-123"}
        mock_post.return_value.status_code = 202
        mock_post.return_value.text = ""

        client = _GraphMailClient()
        client.send(
            subject="Test subject",
            body="Plain body",
            to=["ops@example.com"],
            html_body="<p>HTML body</p>",
        )

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["message"]["subject"], "Test subject")
        self.assertEqual(payload["message"]["body"]["contentType"], "HTML")
        self.assertEqual(payload["message"]["body"]["content"], "<p>HTML body</p>")
        self.assertEqual(
            payload["message"]["toRecipients"][0]["emailAddress"]["address"],
            "ops@example.com",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token-123")

    @patch("django_jt.backends.email.graph.msal.PublicClientApplication")
    def test_get_access_token_requires_cached_account(self, mock_app_cls):
        mock_app = mock_app_cls.return_value
        mock_app.get_accounts.return_value = []

        client = _GraphMailClient()
        with self.assertRaises(GraphAuthError):
            client.get_access_token()

    @patch("django_jt.backends.email.graph.requests.post")
    @patch("django_jt.backends.email.graph.msal.PublicClientApplication")
    def test_send_raises_on_graph_error(self, mock_app_cls, mock_post):
        mock_app = mock_app_cls.return_value
        mock_app.get_accounts.return_value = [{"username": "andy@new901.io"}]
        mock_app.acquire_token_silent.return_value = {"access_token": "token-123"}
        mock_post.return_value.status_code = 403
        mock_post.return_value.text = "Forbidden"

        client = _GraphMailClient()
        with self.assertRaises(GraphSendError):
            client.send(
                subject="Test",
                body="Body",
                to=["ops@example.com"],
            )


@override_settings(
    MS_GRAPH_CLIENT_ID="client-id",
    MS_GRAPH_TENANT_ID="tenant-id",
)
class GraphEmailBackendTests(SimpleTestCase):
    @patch("django_jt.backends.email.graph._GraphMailClient")
    def test_send_plain_text_message(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        backend = GraphEmailBackend()
        message = EmailMessage(
            subject="Alert",
            body="Plain text body",
            from_email="andy@new901.io",
            to=["ops@example.com"],
        )
        sent = backend.send_messages([message])

        self.assertEqual(sent, 1)
        mock_client.send.assert_called_once_with(
            subject="Alert",
            body="Plain text body",
            to=["ops@example.com"],
            html_body=None,
        )

    @patch("django_jt.backends.email.graph._GraphMailClient")
    def test_send_html_alternative(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        backend = GraphEmailBackend()
        message = EmailMultiAlternatives(
            subject="Reset",
            body="Plain fallback",
            from_email="andy@new901.io",
            to=["user@example.com"],
        )
        message.attach_alternative("<p>HTML body</p>", "text/html")

        sent = backend.send_messages([message])

        self.assertEqual(sent, 1)
        mock_client.send.assert_called_once_with(
            subject="Reset",
            body="Plain fallback",
            to=["user@example.com"],
            html_body="<p>HTML body</p>",
        )

    @patch("django_jt.backends.email.graph._GraphMailClient")
    def test_fail_silently_skips_failed_messages(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.send.side_effect = GraphSendError("boom")

        backend = GraphEmailBackend(fail_silently=True)
        message = EmailMessage(
            subject="Alert",
            body="Body",
            from_email="andy@new901.io",
            to=["ops@example.com"],
        )
        sent = backend.send_messages([message])

        self.assertEqual(sent, 0)
        mock_client.send.assert_called_once()

    @patch("django_jt.backends.email.graph._GraphMailClient")
    def test_raises_when_not_fail_silently(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.send.side_effect = GraphSendError("boom")

        backend = GraphEmailBackend(fail_silently=False)
        message = EmailMessage(
            subject="Alert",
            body="Body",
            from_email="andy@new901.io",
            to=["ops@example.com"],
        )

        with self.assertRaises(GraphSendError):
            backend.send_messages([message])

    @patch("django_jt.backends.email.graph._GraphMailClient")
    @override_settings(EMAIL_RECIPIENTS_OVERRIDE=["staging@example.com"])
    def test_recipient_override(self, mock_client_cls):
        mock_client = mock_client_cls.return_value

        backend = GraphEmailBackend()
        message = EmailMessage(
            subject="Alert",
            body="Body",
            from_email="noreply@example.com",
            to=["real-user@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        backend.send_messages([message])

        mock_client.send.assert_called_once_with(
            subject="Alert",
            body="Body",
            to=["staging@example.com"],
            html_body=None,
        )
        self.assertEqual(message.cc, [])
        self.assertEqual(message.bcc, [])
