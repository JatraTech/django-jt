from drf_standardized_errors.formatter import ExceptionFormatter as ExceptionFormatter_
from drf_standardized_errors.types import ErrorResponse


def error_items(errors) -> list[dict]:
    """Every error as ``{code, detail, attr}`` (``attr`` is the field path, e.g. ``contact.phone``)."""
    return [{"code": e.code, "detail": e.detail, "attr": e.attr} for e in errors]


def _request_id(context) -> str | None:
    request = (context or {}).get("request")
    request_id = getattr(getattr(request, "_request", request), "request_id", None)
    if request_id:
        return request_id
    from django_jt.request_id import get_request_id

    return get_request_id()


class ExceptionFormatter(ExceptionFormatter_):
    """Error envelope plus ``errors``: every error, so a form can mark all bad fields at once.

    ``{"success": false, "type": "validation_error", "code": ..., "error": ..., "field": ..., "index": null,
       "errors": [{"code": ..., "detail": ..., "attr": ...}, ...], "request_id": "..."}``
    """

    def format_error_response(self, error_response: ErrorResponse):
        if not error_response.errors:
            from django.utils.translation import gettext
            from drf_standardized_errors.types import Error

            error_response.errors = [
                Error("invalid", gettext("Check the information and try again."), None)
            ]
        error = error_response.errors[0]
        return {
            "success": False,
            "type": error_response.type,
            "code": error.code,
            "error": error.detail,
            "field": error.attr,
            "index": None,
            "errors": error_items(error_response.errors),
            "request_id": _request_id(self.context),
        }


class ScrappingException(Exception):
    def __init__(self, message="", data=None, *args: object) -> None:
        super().__init__(message, *args)
        self.data = data or {}
