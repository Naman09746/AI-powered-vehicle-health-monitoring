"""
API versioning middleware and utilities for the Vehicle Health Monitor.

Provides:
- ``APIVersionMiddleware`` — reads ``Accept-Version`` header or URL prefix,
  injects ``Sunset`` and ``Deprecation`` headers for deprecated versions.
- ``API_DEPRECATION`` config mapping versions to sunset dates.
- ``create_versioned_router()`` helper that creates an ``APIRouter`` with
  automatic deprecation warnings via response headers.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from api.api_version import APIVersion

# ── Deprecation schedule ──────────────────────────────────────────
# Maps deprecated API versions to their sunset dates (ISO 8601).
# Versions not listed here are considered current and stable.

API_DEPRECATION: dict[str, dict[str, str]] = {
    "1.0": {
        "sunset": "2027-01-01",
        "deprecation_date": "2026-06-15",
        "migration_advice": "Upgrade to version 2.0. See https://docs.vehiclehealth.example.com/migration/v1-to-v2",
    },
}


def _get_version_from_accept_header(request: Request) -> str | None:
    """Extract the API version from the ``Accept-Version`` header."""
    return request.headers.get("Accept-Version")


def _get_version_from_url_prefix(path: str) -> str | None:
    """Extract the API version from a URL path prefix (e.g. ``/api/v1/``)."""
    if path.startswith("/api/v1/") or path == "/api/v1":
        return "1.0"
    if path.startswith("/api/v2/") or path == "/api/v2":
        return "2.0"
    return None


def _resolve_api_version(request: Request) -> str | None:
    """Resolve the API version from header or URL prefix, header taking precedence."""
    version = _get_version_from_accept_header(request)
    if version:
        return version
    return _get_version_from_url_prefix(request.url.path)


# ── Middleware ─────────────────────────────────────────────────────


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Middleware that resolves the API version and injects deprecation headers.

    Behaviour:
    1. Reads ``Accept-Version`` header or infers version from ``/api/v1/``,
       ``/api/v2/`` URL prefix.
    2. Stores the resolved version as ``request.state.api_version``.
    3. If the resolved version is deprecated, injects:
       - ``Deprecation: true`` header
       - ``Sunset: <date>`` header
       - ``X-Deprecated-Version: <version>`` header
    4. If *no* version is specified for a versioned endpoint, defaults to
       the latest stable version and injects an informational header.

    Register this middleware **after** ``CorrelationIDMiddleware`` and
    **before** your route handlers.
    """

    def __init__(self, app: ASGIApp, default_version: str = "2.0") -> None:
        super().__init__(app)
        self.default_version = default_version

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Only process API paths
        path = request.url.path
        version = _resolve_api_version(request)

        if version is None and path.startswith("/api/"):
            # No explicit version — use default
            version = self.default_version

        # Store version on request state for downstream use
        request.state.api_version = version or self.default_version

        # Process the request
        response = await call_next(request)

        # Inject deprecation headers if applicable
        if version and version in API_DEPRECATION:
            deprecation_info = API_DEPRECATION[version]
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = deprecation_info["sunset"]
            response.headers["X-Deprecated-Version"] = version
            response.headers["X-Deprecation-Advice"] = deprecation_info[
                "migration_advice"
            ]
            _log_deprecated_access(request, version, deprecation_info)

        return response


def _log_deprecated_access(
    request: Request, version: str, deprecation_info: dict[str, str]
) -> None:
    """Log a warning when a deprecated API version is accessed."""
    from core.logger import get_logger

    log = get_logger("api.versioning")
    log.warning(
        "Deprecated API version %s accessed: %s %s (sunset: %s)",
        version,
        request.method,
        request.url.path,
        deprecation_info["sunset"],
    )


# ── Sunset header injection ───────────────────────────────────────


def add_sunset_header(response: Response, sunset_date: str) -> None:
    """Inject a ``Sunset`` header on a response."""
    response.headers["Sunset"] = sunset_date


# ── Versioned router helper ───────────────────────────────────────


def create_versioned_router(
    *,
    prefix: str,
    tags: list[str] | None = None,
    version: APIVersion = APIVersion.V2,
    deprecated: bool = False,
    sunset_date: str | None = None,
) -> APIRouter:
    """Create an ``APIRouter`` with built-in deprecation awareness.

    The router automatically injects ``Deprecation`` and ``Sunset``
    response headers when ``deprecated=True`` is passed.

    Args:
        prefix: URL prefix (e.g. ``/api/v2/vehicles``).
        tags: OpenAPI tags for route grouping.
        version: The API version this router serves.
        deprecated: If ``True``, all routes get deprecation headers.
        sunset_date: ISO 8601 date when the version is fully removed.

    Returns:
        An ``APIRouter`` instance with a custom response header
        injection hook.
    """
    router = APIRouter(
        prefix=prefix,
        tags=tags or [],
    )

    # Store metadata on the router instance for middleware inspection
    router.api_version = version.value  # type: ignore[attr-defined]
    router.deprecated = deprecated  # type: ignore[attr-defined]
    router.sunset_date = sunset_date  # type: ignore[attr-defined]

    return router


def register_versioning(app: FastAPI) -> None:
    """Register API versioning middleware and error handlers on the app.

    Call from ``setup_middleware`` or directly in ``main.py`` after
    creating the FastAPI instance.

    Args:
        app: The FastAPI application instance.
    """
    # Add versioning middleware
    app.add_middleware(APIVersionMiddleware, default_version=APIVersion.latest().value)

    # Register deprecated-version error handler
    from api.api_version import DeprecatedApiVersion, deprecated_api_version_handler

    app.add_exception_handler(DeprecatedApiVersion, deprecated_api_version_handler)  # type: ignore[arg-type]
