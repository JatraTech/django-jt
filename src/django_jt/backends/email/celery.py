"""Optional Celery hand-off for outbound email backends."""

from __future__ import annotations

from typing import Any


def _celery_worker_ping() -> bool:
    try:
        from celery import current_app

        return bool(current_app.control.inspect().ping())
    except Exception:
        return False


def should_queue_email_tasks() -> bool:
    from django.conf import settings

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return True
    return _celery_worker_ping()


def dispatch_async(task: Any, *args: Any, **kwargs: Any) -> None:
    task.delay(*args, **kwargs)
