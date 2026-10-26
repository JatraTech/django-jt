"""
Request ids: one id per request, quoted in bug reports and found in every log line.

* :class:`RequestIdMiddleware` (first in ``MIDDLEWARE``) accepts an incoming ``X-Request-ID`` when it
  looks like an id (8 to 128 letters, digits, ``-``, ``_``, ``.`` or ``:``; anything else is replaced,
  never trusted), or makes one (32 hex characters). It answers it on **every** response in
  ``X-Request-ID``, and every error envelope carries it as ``request_id``.
* :class:`RequestIdFilter` writes ``request_id`` on every log line made while the request is handled,
  including Django's own "Unauthorized: ..." lines, which are logged after the middleware returns:
  the id is cleared on ``request_finished``, not when the middleware ends.
* Celery tasks queued during a request carry the id in a message header when the host calls
  :func:`connect_celery`.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar

HEADER = "X-Request-ID"
META_KEY = "HTTP_X_REQUEST_ID"
CELERY_HEADER = "request_id"

_VALID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{7,127}$")
_current: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex


def clean(value) -> str | None:
    """``value`` if it is an acceptable request id, else None (callers make a new one)."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _VALID.match(value) else None


def get_request_id() -> str | None:
    """The id of the request (or the task it queued) being handled on this thread, if any."""
    return _current.get()


def set_request_id(value: str | None) -> None:
    _current.set(value)


def _clear(**_kwargs) -> None:
    _current.set(None)


def _with_request_id(response, request_id: str) -> None:
    """Add ``request_id`` to a JSON error envelope that was built outside DRF (no-op otherwise)."""
    if response.status_code < 400 or getattr(response, "streaming", False):
        return
    if not (response.get("Content-Type") or "").startswith("application/json"):
        return
    try:
        body = json.loads(response.content or b"null")
    except (ValueError, UnicodeDecodeError):
        return
    if not isinstance(body, dict) or body.get("success") is not False or body.get("request_id"):
        return
    body["request_id"] = request_id
    response.content = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if response.has_header("Content-Length"):
        response["Content-Length"] = str(len(response.content))


class RequestIdMiddleware:
    """First in ``MIDDLEWARE``: every response carries the id."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = clean(request.META.get(META_KEY)) or new_request_id()
        request.request_id = request_id
        _current.set(request_id)
        response = self.get_response(request)
        _with_request_id(response, request_id)
        response[HEADER] = request_id
        return response


class RequestIdFilter(logging.Filter):
    """Adds ``request_id`` to every record made while a request (or a task it queued) is handled."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            request_id = _current.get()
            if request_id:
                record.request_id = request_id
        return True


def connect_request_finished() -> None:
    from django.core.signals import request_finished

    request_finished.connect(_clear, dispatch_uid="django_jt.request_id.clear")


def _before_publish(headers=None, **_kwargs) -> None:
    request_id = _current.get()
    if request_id and isinstance(headers, dict):
        headers.setdefault(CELERY_HEADER, request_id)


def _task_prerun(task=None, **_kwargs) -> None:
    request = getattr(task, "request", None)
    value = getattr(request, CELERY_HEADER, None) if request is not None else None
    if value is None and request is not None:
        value = (getattr(request, "headers", None) or {}).get(CELERY_HEADER)
    if value or not getattr(request, "is_eager", False):
        _current.set(clean(value))


def _task_postrun(task=None, **_kwargs) -> None:
    if not getattr(getattr(task, "request", None), "is_eager", False):
        _current.set(None)


def connect_celery() -> None:
    from celery.signals import before_task_publish, task_postrun, task_prerun

    before_task_publish.connect(_before_publish, dispatch_uid="django_jt.request_id.publish", weak=False)
    task_prerun.connect(_task_prerun, dispatch_uid="django_jt.request_id.prerun", weak=False)
    task_postrun.connect(_task_postrun, dispatch_uid="django_jt.request_id.postrun", weak=False)
