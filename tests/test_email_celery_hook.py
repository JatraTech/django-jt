from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from django_jt.backends.email.celery import should_queue_email_tasks


class EmailCeleryHookTests(SimpleTestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_queues_when_eager(self):
        self.assertTrue(should_queue_email_tasks())

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("django_jt.backends.email.celery._celery_worker_ping", return_value=True)
    def test_queues_when_worker_ping_ok(self, _mock_ping):
        self.assertTrue(should_queue_email_tasks())

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("django_jt.backends.email.celery._celery_worker_ping", return_value=False)
    def test_sync_when_no_worker(self, _mock_ping):
        self.assertFalse(should_queue_email_tasks())
