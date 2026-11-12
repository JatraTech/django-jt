"""Celery tasks for Gmail and Graph backends (import from host celery autodiscover or app.tasks)."""

from __future__ import annotations

from django.core.mail.message import EmailMessage

try:
    from celery import shared_task
except ImportError:

    def shared_task(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator


@shared_task(serializer="pickle")
def send_gmail_emails(email_messages: list[EmailMessage], fail_silently: bool = False) -> int:
    from django_jt.backends.email.gmail import GmailBackend

    return GmailBackend.send_batch_emails(
        email_messages,
        fail_silently=fail_silently,
    )


@shared_task(serializer="pickle")
def send_graph_emails(email_messages: list[EmailMessage], fail_silently: bool = False) -> int:
    from django_jt.backends.email.graph import GraphEmailBackend

    return GraphEmailBackend.send_batch_emails(
        email_messages,
        fail_silently=fail_silently,
    )
