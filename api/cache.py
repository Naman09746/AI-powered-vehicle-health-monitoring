"""
Redis response caching middleware for FastAPI.

Caches GET responses with ETag and Cache-Control headers.
Supports invalidation via key patterns and webhook events.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logger import get_logger

log = get_logger("cache")

# Paths that should NOT be cached
UNCACHED_PATHS = {
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/ws",
}

# Paths that can be cached with short TTL
CACHEABLE_PATHS = {
    "/api/v1/vehicles",
    "/api/v1/dashboard",
    "/api/v1/fleet",
    "/api/v1/reports",
    "/api/v1/history",
    "/api/v1/alerts",
    "/api/v1/predictions",
    "/api/v1/ml/models",
}


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Response caching middleware using Redis.

    Caches successful GET responses for configured paths.
    Uses ETag for conditional requests and Cache-Control for browser caching.
    """

    def __init__(
        self,
        app,
        redis_client,
        default_ttl: int = 30,
        max_ttl: int = 300,
    ):
        super().__init__(app)
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.max_ttl = max_ttl

    def _should_cache(self, request: Request) -> bool:
        """Determine if request should be cached."""
        # Only cache GET requests
        if request.method != "GET":
            return False

        # Skip uncached paths
        path = request.url.path
        if path in UNCACHED_PATHS:
            return False

        # Check if path matches cacheable patterns
        return any(path.startswith(pattern) for pattern in CACHEABLE_PATHS)

    def _get_cache_key(self, request: Request) -> str:
        """Generate cache key from request."""
        # Include path, query params, and user ID (from auth)
        user_id = getattr(request.state, "user_id", "anonymous")
        key_parts = [
            "cache",
            request.url.path,
            request.url.query,
            f"user:{user_id}",
        ]
        return ":".join(key_parts)

    def _generate_etag(self, body: bytes) -> str:
        """Generate ETag from response body."""
        return f'W/"{hashlib.md5(body).hexdigest()[:16]}"'

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._should_cache(request):
            return await call_next(request)

        # Check If-None-Match header
        if_none_match = request.headers.get("If-None-Match")
        cache_key = self._get_cache_key(request)

        try:
            # Try to get cached response
            cached = await self.redis.get(cache_key)
            if cached:
                cached_data = json.loads(cached)
                etag = cached_data.get("etag")

                # Return 304 if ETag matches
                if if_none_match and if_none_match == etag:
                    return Response(
                        status_code=304,
                        headers={
                            "ETag": etag,
                            "Cache-Control": f"max-age={self.default_ttl}",
                        },
                    )

                # Return cached response
                response = Response(
                    content=cached_data["body"],
                    status_code=cached_data["status"],
                    media_type=cached_data.get("media_type", "application/json"),
                    headers={
                        "ETag": etag,
                        "Cache-Control": f"max-age={self.default_ttl}",
                        "X-Cache": "HIT",
                    },
                )
                return response
        except Exception:
            log.exception("Cache read error, bypassing cache")

        # No cache hit — proceed with request
        response = await call_next(request)

        # Cache successful GET responses
        if response.status_code == 200:
            try:
                # Collect body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk

                # Re-create response with collected body
                etag = self._generate_etag(body)
                media_type = response.media_type or "application/json"

                # Determine TTL based on path
                ttl = self.default_ttl
                if request.url.path.startswith("/api/v1/ml/"):
                    ttl = self.max_ttl  # Models change less frequently

                cached_data = {
                    "body": body.decode(),
                    "status": response.status_code,
                    "media_type": media_type,
                    "etag": etag,
                }

                await self.redis.setex(cache_key, ttl, json.dumps(cached_data))

                # Return response with cache headers
                return Response(
                    content=body,
                    status_code=response.status_code,
                    media_type=media_type,
                    headers={
                        **dict(response.headers),
                        "ETag": etag,
                        "Cache-Control": f"max-age={ttl}",
                        "X-Cache": "MISS",
                    },
                )
            except Exception:
                log.exception("Cache write error")

        return response


async def invalidate_cache_pattern(redis_client, pattern: str) -> int:
    """Invalidate all cache keys matching pattern."""
    try:
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
            if keys:
                deleted += await redis_client.delete(*keys)
            if cursor == 0:
                break
        return deleted
    except Exception:
        log.exception("Cache invalidation error")
        return 0


async def invalidate_user_cache(redis_client, user_id: int) -> int:
    """Invalidate all cache entries for a specific user."""
    return await invalidate_cache_pattern(redis_client, f"cache:*:user:{user_id}:*")


async def invalidate_vehicle_cache(redis_client, vehicle_id: int, user_id: int) -> int:
    """Invalidate cache for a specific vehicle."""
    return await invalidate_cache_pattern(
        redis_client, f"cache:*/vehicles/{vehicle_id}*:user:{user_id}:*"
    )
