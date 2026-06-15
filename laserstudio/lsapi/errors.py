"""Typed exceptions raised by the :class:`~laserstudio.lsapi.lsapi.LSAPI` client.

The REST server returns errors with a normalized body::

    {"error": {"code": "...", "message": "...", "details": {...}}}

:func:`raise_for_response` inspects an HTTP response and, when it is an error,
raises the matching :class:`LSAPIError` subclass (reconstructed from the
machine-readable ``code``). This gives scripts and the future MCP server
explicit, catchable error types instead of having to inspect raw HTTP status
codes or response bodies.

This module is deliberately free of any PyQt dependency, like the rest of the
``lsapi`` package.
"""

from __future__ import annotations

from typing import Any

import requests


class LSAPIError(Exception):
    """Base class for every error reported by the LaserStudio REST API."""

    #: Machine-readable code as returned by the server. Subclasses override it.
    code: str = "LSAPI_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.status_code = status_code
        self.details: dict[str, Any] = details or {}


class LSAPIConnectionError(LSAPIError):
    """The client could not reach the LaserStudio server."""

    code = "CONNECTION_ERROR"


class InvalidParameter(LSAPIError):
    """A provided parameter is missing or invalid (HTTP 400)."""

    code = "INVALID_PARAMETER"


class InstrumentNotFound(LSAPIError):
    """No instrument matches the requested label (HTTP 404)."""

    code = "INSTRUMENT_NOT_FOUND"


class MemoryPointNotFound(LSAPIError):
    """No memory point matches the requested index (HTTP 404)."""

    code = "MEMORY_POINT_NOT_FOUND"


class DeviceUnavailable(LSAPIError):
    """A required device is not available (HTTP 503)."""

    code = "DEVICE_UNAVAILABLE"


class Conflict(LSAPIError):
    """The action cannot be performed in the current state (HTTP 409)."""

    code = "CONFLICT"


class ActionNotImplemented(LSAPIError):
    """The requested action is not implemented yet (HTTP 501)."""

    code = "NOT_IMPLEMENTED"


# Mapping from server-side ``code`` to the matching client exception class.
_CODE_TO_EXCEPTION: dict[str, type[LSAPIError]] = {
    cls.code: cls
    for cls in (
        InvalidParameter,
        InstrumentNotFound,
        MemoryPointNotFound,
        DeviceUnavailable,
        Conflict,
        ActionNotImplemented,
    )
}


def raise_for_response(response: requests.Response) -> None:
    """Raise a typed :class:`LSAPIError` if ``response`` is an HTTP error.

    Successful responses (2xx) return ``None`` and leave the caller free to
    decode the payload (JSON, PNG, numpy array, ...).

    :param response: The HTTP response returned by :mod:`requests`.
    :raises LSAPIError: A subclass matching the server-reported ``code`` when
        available, otherwise a generic :class:`LSAPIError`.
    """
    if response.ok:
        return

    code: str | None = None
    message: str | None = None
    details: dict[str, Any] = {}

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            raw_details = error.get("details")
            if isinstance(raw_details, dict):
                details = raw_details
        elif isinstance(error, str):
            message = error
        elif isinstance(payload.get("detail"), str):
            # FastAPI default error shape (e.g. unknown route): {"detail": "..."}
            message = payload["detail"]
        elif isinstance(payload.get("message"), str):
            message = payload["message"]

    if message is None:
        message = (response.text or response.reason or "Unknown error").strip()

    exc_class = _CODE_TO_EXCEPTION.get(code or "", LSAPIError)
    raise exc_class(
        message,
        code=code,
        status_code=response.status_code,
        details=details,
    )


__all__ = [
    "LSAPIError",
    "LSAPIConnectionError",
    "InvalidParameter",
    "InstrumentNotFound",
    "MemoryPointNotFound",
    "DeviceUnavailable",
    "Conflict",
    "ActionNotImplemented",
    "raise_for_response",
]
