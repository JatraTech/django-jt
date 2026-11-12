from unittest.mock import patch

from django.core.mail import EmailMessage
from django.test import SimpleTestCase

from django_jt.backends.email.gmail import GmailBackend


class GmailEmailBackendTests(SimpleTestCase):
    @patch("django_jt.backends.email.gmail.should_queue_email_tasks", return_value=False)
    @patch.object(GmailBackend, "send_batch_emails", return_value=0)
    def test_fail_silently_skips_failed_batch(self, _mock_batch, _mock_queue):
        backend = GmailBackend(fail_silently=True)
        message = EmailMessage(
            subject="Alert",
            body="Body",
            from_email="noreply@example.com",
            to=["ops@example.com"],
        )
        sent = backend.send_messages([message])
        self.assertEqual(sent, 0)

    @patch("django_jt.backends.email.gmail.should_queue_email_tasks", return_value=False)
    @patch.object(GmailBackend, "send_batch_emails", side_effect=RuntimeError("boom"))
    def test_raises_when_not_fail_silently(self, _mock_batch, _mock_queue):
        backend = GmailBackend(fail_silently=False)
        message = EmailMessage(
            subject="Alert",
            body="Body",
            from_email="noreply@example.com",
            to=["ops@example.com"],
        )
        with self.assertRaises(RuntimeError):
            backend.send_messages([message])

    @patch("django_jt.backends.email.gmail.should_queue_email_tasks", return_value=False)
    @patch.object(GmailBackend, "send_batch_emails", return_value=1)
    def test_send_success_returns_count(self, _mock_batch, _mock_queue):
        backend = GmailBackend()
        message = EmailMessage(
            subject="Alert",
            body="Body",
            from_email="noreply@example.com",
            to=["ops@example.com"],
        )
        sent = backend.send_messages([message])
        self.assertEqual(sent, 1)
