"""
Middleware & global exception handlers for the FastAPI application.

Provides:
- Correlation ID injection (request → response header + log context)
- RFC 7807 Problem Details for all HTTP errors
- Rate limiting (slowapi)
- Request timing metrics
- Response compression (gzip/brotli)
- Response caching with Redis (ETag, Cache-Control)
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import ALLOWED_ORIGINS

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    _SLOWAPI_AVAILABLE = True
except ImportError:
    _SLOWAPI_AVAILABLE = False


# ── Correlation ID ─────────────────────────────────────────────


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Inject X-Correlation-ID header (from request or generated) into request.state
    and echo it back on the response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = cid

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = int((time.perf_counter() - start) * 1000)

        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Response-Time-Ms"] = str(elapsed)
        return response


# ── RFC 7807 Problem Details ───────────────────────────────────

PROBLEM_CONTENT_TYPE = "application/problem+json"


def _problem_response(
    status: int,
    title: str,
    detail: str,
    instance: str | None = None,
    extra: dict | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://httpstatuses.org/{status}",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE
    )


def add_exception_handlers(app: FastAPI) -> None:
    """Register RFC 7807 exception handlers on the given FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            errors.append(
                {
                    "field": " -> ".join(str(l) for l in err.get("loc", [])),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )
        return _problem_response(
            status=422,
            title="Unprocessable Entity",
            detail="Request validation failed",
            instance=request.url.path,
            extra={"errors": errors},
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return _problem_response(
            status=404,
            title="Not Found",
            detail=f"The requested resource '{request.url.path}' was not found",
            instance=request.url.path,
        )

    @app.exception_handler(405)
    async def method_not_allowed_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return _problem_response(
            status=405,
            title="Method Not Allowed",
            detail=f"Method {request.method} not allowed for '{request.url.path}'",
            instance=request.url.path,
        )

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
        from core.logger import get_logger

        log = get_logger("api.error")
        log.exception(
            "Unhandled exception: %s",
            exc,
            extra={"correlation_id": getattr(request.state, "correlation_id", None)},
        )
        return _problem_response(
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred",
            instance=request.url.path,
        )


# ── Response Caching ───────────────────────────────────────────

CACHEABLE_METHODS = {"GET", "HEAD"}
CACHEABLE_STATUS = {200, 304}


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """Redis-backed response cache with ETag and Cache-Control support.

    Caches successful GET/HEAD responses for configured TTL.
    Respects Cache-Control: no-store and private responses.
    """

    def __init__(
        self, app: ASGIApp, redis_url: str | None = None, default_ttl: int = 60
    ):
        super().__init__(app)
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis = None

    async def _get_redis(self):
        if self._redis is None and self.redis_url:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    self.redis_url,
                    socket_connect_timeout=2,
                    max_connections=20,
                    decode_responses=True,
                )
                await self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _cache_key(self, request: Request) -> str:
        """Generate cache key from method, path, query params, and user."""
        user_id = getattr(request.state, "user_id", "anonymous")
        key_parts = [
            request.method,
            request.url.path,
            str(sorted(request.query_params.items())),
            str(user_id),
        ]
        return "cache:" + hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:32]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Only cache GET/HEAD requests
        if request.method not in CACHEABLE_METHODS:
            return await call_next(request)

        # Check for no-cache directives
        if request.headers.get("Cache-Control", "").lower().find("no-cache") >= 0:
            return await call_next(request)

        redis = await self._get_redis()
        if not redis:
            return await call_next(request)

        cache_key = self._cache_key(request)

        # Try to get cached response
        try:
            cached = await redis.get(cache_key)
            if cached:
                cached_data = json.loads(cached)
                # Check ETag
                if_none_match = request.headers.get("If-None-Match")
                if if_none_match and if_none_match == cached_data.get("etag"):
                    return Response(
                        status_code=304, headers={"ETag": cached_data["etag"]}
                    )

                # Return cached response
                response = Response(
                    content=cached_data["body"],
                    status_code=cached_data["status"],
                    media_type=cached_data["media_type"],
                    headers=cached_data.get("headers", {}),
                )
                response.headers["X-Cache"] = "HIT"
                response.headers["ETag"] = cached_data["etag"]
                return response
        except Exception:
            pass  # Cache miss or error — continue to fetch fresh

        # Fetch fresh response
        response = await call_next(request)

        # Only cache successful responses
        if response.status_code not in CACHEABLE_STATUS:
            return response

        # Check response cache control
        cache_control = response.headers.get("Cache-Control", "")
        if "no-store" in cache_control.lower() or "private" in cache_control.lower():
            return response

        # Generate ETag from response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # Reconstruct response to allow re-reading
        etag = hashlib.md5(body).hexdigest()

        # Cache the response
        try:
            cache_data = {
                "body": body.decode("utf-8", errors="replace"),
                "status": response.status_code,
                "media_type": response.media_type,
                "headers": dict(response.headers),
                "etag": etag,
            }
            await redis.setex(cache_key, self.default_ttl, json.dumps(cache_data))
        except Exception:
            pass  # Fail silently

        # Return response with ETag
        response.headers["ETag"] = etag
        response.headers["X-Cache"] = "MISS"
        return Response(
            content=body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=response.headers,
        )


# ── Rate limiter ───────────────────────────────────────────────


def setup_rate_limiter(app: FastAPI) -> None:
    """Enable rate limiting via slowapi (safe no-op if package missing)."""
    if not _SLOWAPI_AVAILABLE:
        return

    limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)


# ── Bootstrap all middleware ───────────────────────────────────


def setup_middleware(app: FastAPI) -> None:
    """Register all middleware and exception handlers on the app."""
    # Order matters: outermost first (last to execute).
    # 1. Correlation ID (outermost)
    app.add_middleware(CorrelationIDMiddleware)
    # 2. CORS
    # Merge configured origins + hardcoded production origin as safety net
    # (prevents misconfiguration when the ALLOWED_ORIGINS env var omits the
    #  production frontend URL — a common pitfall on Render/Vercel deploys)
    _cors_origins = [o for o in ALLOWED_ORIGINS if o and o != "*"]
    _cors_origins.extend([
        "https://ai-powered-vehicle-health-monitorin.vercel.app",
        "https://ai-powered-vehicle-health-monitoring.vercel.app",
        "http://localhost:3000",
        "http://localhost:8000",
    ])
    _cors_origins = list(dict.fromkeys(_cors_origins))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 3. Compression (gzip)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    # 4. Rate limiter
    setup_rate_limiter(app)
    # 5. Response cache (innermost, before request reaches routers)
    from core.config import REDIS_URL

    if REDIS_URL and REDIS_URL != "redis://localhost:6379/0":
        app.add_middleware(ResponseCacheMiddleware, redis_url=REDIS_URL, default_ttl=60)
    # 6. Exception handlers
    add_exception_handlers(app)
