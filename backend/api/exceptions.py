"""Gives framework errors the same {"error": message} shape as the API's own errors."""

from typing import Any

from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler

THROTTLED_MESSAGE = "Too many requests from this connection. Please wait a few minutes and try again."
FALLBACK_MESSAGE = "The request could not be processed."


def handle_api_exception(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, Throttled):
        message = THROTTLED_MESSAGE
    else:
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        message = str(detail) if detail else FALLBACK_MESSAGE
    response.data = {"error": message}
    return response
