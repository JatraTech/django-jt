import json
import logging
import re

import pytest
from django.core.signals import request_finished
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory

from django_jt.request_id import (
    HEADER,
    RequestIdFilter,
    RequestIdMiddleware,
    get_request_id,
    set_request_id,
)

GENERATED = re.compile(r"^[0-9a-f]{32}$")


def _middleware(get_response):
    return RequestIdMiddleware(get_response)


def test_a_valid_incoming_id_is_kept():
    incoming = "qa-2026-10-02-0001"

    def view(request):
        assert request.request_id == incoming
        assert get_request_id() == incoming
        return HttpResponse("ok")

    request = RequestFactory().get("/", HTTP_X_REQUEST_ID=incoming)
    response = _middleware(view)(request)
    assert response[HEADER] == incoming


def test_an_unusable_incoming_id_is_replaced():
    def view(request):
        return HttpResponse("ok")

    request = RequestFactory().get("/", HTTP_X_REQUEST_ID="short")
    response = _middleware(view)(request)
    assert GENERATED.match(response[HEADER])
    assert response[HEADER] != "short"


def test_a_missing_id_is_generated():
    def view(request):
        return HttpResponse("ok")

    first = _middleware(view)(RequestFactory().get("/"))
    second = _middleware(view)(RequestFactory().get("/"))
    assert GENERATED.match(first[HEADER])
    assert GENERATED.match(second[HEADER])
    assert first[HEADER] != second[HEADER]


def test_json_error_envelope_gets_the_id():
    def view(request):
        return JsonResponse({"success": False, "error": "nope"}, status=400)

    request = RequestFactory().get("/", HTTP_X_REQUEST_ID="qa-2026-10-02-0001")
    response = _middleware(view)(request)
    assert json.loads(response.content)["request_id"] == "qa-2026-10-02-0001"
    assert response[HEADER] == "qa-2026-10-02-0001"


def test_success_json_is_left_alone():
    def view(request):
        return JsonResponse({"ok": True})

    response = _middleware(view)(RequestFactory().get("/"))
    assert "request_id" not in json.loads(response.content)


def test_log_filter_stamps_the_current_id():
    record = logging.LogRecord("django_jt.test", logging.INFO, __file__, 1, "hello", (), None)
    set_request_id("qa-2026-10-02-0001")
    try:
        assert RequestIdFilter().filter(record) is True
    finally:
        set_request_id(None)
    assert record.request_id == "qa-2026-10-02-0001"


@pytest.mark.django_db
def test_request_finished_clears_the_id():
    set_request_id("qa-2026-10-02-0001")
    request_finished.send(sender=None)
    assert get_request_id() is None
