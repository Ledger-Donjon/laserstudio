"""Domain error hierarchy exposed through the REST API.

These exceptions are the single source of truth for error semantics. They are
raised in the application (GUI) thread, propagated to the Flask thread by the
generic thread-bridge (see :mod:`laserstudio.restserver.server`), and translated
to HTTP responses by a single error handler.

Each exception carries:

* ``code``: a stable, machine-readable identifier (used by the ``lsapi`` client
  to reconstruct a typed Python exception).
* ``http_status``: the HTTP status code to return.
* ``message``: a human-readable explanation.
* ``details``: an optional dict with extra context (e.g. the faulty label).

The serialized error body is always::

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any


class LaserStudioError(Exception):
    """Base class for every error exposed through the REST API."""

    code: str = "LASERSTUDIO_ERROR"
    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ):
        resolved = message or (self.__class__.__doc__ or self.code).strip()
        super().__init__(resolved)
        self.message = resolved
        self.details: dict[str, Any] = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error to the normalized error body."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class InvalidParameterError(LaserStudioError):
    """A provided parameter is missing or invalid."""

    code = "INVALID_PARAMETER"
    http_status = HTTPStatus.BAD_REQUEST


class InstrumentNotFoundError(LaserStudioError):
    """No instrument matches the requested label."""

    code = "INSTRUMENT_NOT_FOUND"
    http_status = HTTPStatus.NOT_FOUND

    def __init__(self, label: str, *, details: dict[str, Any] | None = None):
        merged = {"label": label}
        if details:
            merged.update(details)
        super().__init__(
            f"No instrument matches the label {label!r}.", details=merged
        )


class MemoryPointNotFoundError(LaserStudioError):
    """No memory point matches the requested index."""

    code = "MEMORY_POINT_NOT_FOUND"
    http_status = HTTPStatus.NOT_FOUND

    def __init__(self, index: int, *, details: dict[str, Any] | None = None):
        merged: dict[str, Any] = {"index": index}
        if details:
            merged.update(details)
        super().__init__(
            f"No memory point exists at index {index}.", details=merged
        )


class ScanZoneNotFoundError(LaserStudioError):
    """No scan zone matches the requested id."""

    code = "SCAN_ZONE_NOT_FOUND"
    http_status = HTTPStatus.NOT_FOUND

    def __init__(self, zone_id: int, *, details: dict[str, Any] | None = None):
        merged: dict[str, Any] = {"id": zone_id}
        if details:
            merged.update(details)
        super().__init__(
            f"No scan zone exists with id {zone_id}.", details=merged
        )


class DeviceUnavailableError(LaserStudioError):
    """A device required to perform the action is not available."""

    code = "DEVICE_UNAVAILABLE"
    http_status = HTTPStatus.SERVICE_UNAVAILABLE


class ConflictError(LaserStudioError):
    """The action cannot be performed in the current state."""

    code = "CONFLICT"
    http_status = HTTPStatus.CONFLICT


class ActionNotImplementedError(LaserStudioError):
    """The requested action is not implemented yet."""

    code = "NOT_IMPLEMENTED"
    http_status = HTTPStatus.NOT_IMPLEMENTED


__all__ = [
    "LaserStudioError",
    "InvalidParameterError",
    "InstrumentNotFoundError",
    "MemoryPointNotFoundError",
    "ScanZoneNotFoundError",
    "DeviceUnavailableError",
    "ConflictError",
    "ActionNotImplementedError",
]
