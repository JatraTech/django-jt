from django.test import SimpleTestCase


class EmailTaskRegistrationTests(SimpleTestCase):
    def test_email_tasks_registered_after_django_setup(self):
        from celery import current_app

        self.assertIn("django_jt.backends.email.tasks.send_gmail_emails", current_app.tasks)
        self.assertIn("django_jt.backends.email.tasks.send_graph_emails", current_app.tasks)
