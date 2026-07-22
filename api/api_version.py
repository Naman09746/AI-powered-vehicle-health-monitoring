"""
API versioning support for the Vehicle Health Monitor.

Provides:
- ``APIVersion`` enum for supported API versions.
- ``get_api_version()`` dependency that resolves the requested version
  from the ``Accept-Version`` header or URL prefix.
- ``DeprecatedApiVersion`` exception and error handler.
- Version-aware router helpers for deprecation warnings.
"""

from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass

from fastapi import Header, HTTPException, Request, status
from fastapi.responses import JSONResponse


class APIVersion(StrEnum):
    """Supported API versions."""

    V1 = "1.0"
    V2 = "2.0"

    @classmethod
    def latest(cls) -> APIVersion:
        """Return the most recent stable API version."""
        return cls.V2

    @classmethod
    def parse(cls, value: str | None) -> APIVersion:
        """Parse a version string, defaulting to the latest version."""
        if not value:
            return cls.latest()
        for member in cls:
            if member.value == value:
                return member
        # If unrecognised, return latest and let the caller warn
        return cls.latest()


# ── Exception ─────────────────────────────────────────────────────


class DeprecatedApiVersion(HTTPException):
    """Raised when a client requests a deprecated API version.

    The response includes a ``Sunset`` header and a deprecation warning
    in the response body.
    """

    def __init__(
        self,
        version: APIVersion,
        sunset_date: str,
        detail: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
            or f"API version {version.value} is deprecated and will be removed after {sunset_date}. "
            f"Please migrate to {APIVersion.latest().value}.",
            headers={"Sunset": sunset_date, "Deprecation": "true"},
        )
        self.version = version
        self.sunset_date = sunset_date


# ── Dependencies ──────────────────────────────────────────────────


async def get_api_version(
    accept_version: str | None = Header(None, alias="Accept-Version"),
) -> APIVersion:
    """FastAPI dependency that resolves the requested API version.

    Reads the ``Accept-Version`` header.  If absent, defaults to the
    latest stable version.

    Usage::

        @router.get("/vehicles")
        async def list_vehicles(
            api_version: APIVersion = Depends(get_api_version),
        ):
            ...
    """
    return APIVersion.parse(accept_version)


async def get_api_version_strict(
    accept_version: str | None = Header(None, alias="Accept-Version"),
) -> APIVersion:
    """Like ``get_api_version`` but raises 400 for unknown version strings."""
    if accept_version is not None and accept_version not in {
        v.value for v in APIVersion
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported API version '{accept_version}'. "
            f"Supported versions: {[v.value for v in APIVersion]}",
        )
    return APIVersion.parse(accept_version)


# ── Error handler ─────────────────────────────────────────────────


async def deprecated_api_version_handler(
    request: Request, exc: DeprecatedApiVersion
) -> JSONResponse:
    """JSON response for ``DeprecatedApiVersion`` exceptions.

    Includes RFC 8594 ``Deprecation`` and ``Sunset`` headers so that
    HTTP-aware clients can detect deprecation programmatically.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "https://httpstatuses.org/400",
            "title": "Deprecated API Version",
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": request.url.path,
            "deprecated_version": exc.version.value,
            "sunset": exc.sunset_date,
            "migrate_to": APIVersion.latest().value,
        },
        headers={
            "Deprecation": "true",
            "Sunset": exc.sunset_date,
            "X-Deprecated-Version": exc.version.value,
        },
    )
