"""
FastAPI dependency injection — shared across all routers.

Provides:
- ``get_db()``: yields an async DB session
- ``get_current_user()``: validates Bearer token (OAuth2 first, then session) and returns user info
- ``get_optional_user()``: like above but returns None for unauthenticated
- ``get_current_user_ws()``: WebSocket-friendly version with connection-scoped user
- ``sync_to_async()``: runs a sync function off the event loop via thread executor

Uses async SQLAlchemy 2.0 sessions from ``api.database``.
For backward compatibility, sync sessions from ``db`` are used only
where async is unavailable (WebSocket endpoints, sync database tasks).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_async_session
from core.logger import get_logger

log = get_logger("dependencies")

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async database session, committing on success, rolling back on error."""
    async with get_async_session() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Dependency that validates the Bearer token and returns the authenticated user.

    Authentication flow:
    1. Try OAuth2 / Keycloak validation (if ``OAUTH_ENABLED`` is ``True``).
    2. Fall back to session token validation.

    Raises ``HTTPException(401)`` if neither method succeeds.
    """
    token = None
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header (Bearer <token>) or token query parameter",
        )

    # Step 1: Try OAuth2 (Keycloak)
    from auth.oauth2 import get_current_user_oauth2

    # We need to re-parse since we already consumed the dependency
    oauth2_creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )
    oauth2_user = await get_current_user_oauth2(oauth2_creds)
    if oauth2_user is not None:
        return oauth2_user

    # Step 2: Try session token
    from auth.session import validate_session

    user_info = validate_session(token)
    if user_info is not None:
        return user_info

    # Step 3: Neither worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
    )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any] | None:
    """Like ``get_current_user`` but returns ``None`` for unauthenticated requests.

    This is useful for endpoints that have different behaviour for
    authenticated vs. anonymous users (e.g. rate limits, cached responses).
    """
    token = None
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.query_params.get("token")

    if not token:
        return None

    # Step 1: Try OAuth2 (Keycloak)
    from auth.oauth2 import get_current_user_oauth2

    oauth2_creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )
    oauth2_user = await get_current_user_oauth2(oauth2_creds)
    if oauth2_user is not None:
        return oauth2_user

    # Step 2: Try session token
    from auth.session import validate_session

    return validate_session(token)


async def get_current_user_ws(
    websocket: WebSocket,  # noqa: F821
) -> dict[str, Any]:
    """Validate a user from a WebSocket connection's query parameter.

    Usage in a WebSocket endpoint::

        @app.websocket("/ws/vehicles/{vehicle_id}/live")
        async def ws_endpoint(websocket: WebSocket, vehicle_id: int):
            user = await get_current_user_ws(websocket)
            ...

    Expects the token as a query parameter ``?token=<session_or_oauth2_token>``.
    """

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return None  # type: ignore[unreachable]

    # Try OAuth2 first
    from auth.oauth2 import verify_oauth2_token

    payload = verify_oauth2_token(token)
    if payload is not None:
        from auth.oauth2 import oauth2_to_user_dict

        jti = payload.get("jti")
        if jti:
            from auth.token_blocklist import is_blocklisted

            if not await is_blocklisted(jti):
                return oauth2_to_user_dict(payload)
        await websocket.close(code=4001, reason="Token revoked")
        return None

    # Fall back to session token
    from auth.session import validate_session

    user_info = validate_session(token)
    if user_info is not None:
        return user_info

    await websocket.close(code=4001, reason="Invalid or expired token")
    return None  # type: ignore[unreachable]


# ──────────────────────────────────────────────
# Sync-to-async bridge for blocking DB calls
# ──────────────────────────────────────────────


async def sync_to_async(func: Callable, *args, **kwargs) -> Any:
    """Run a synchronous function in a thread executor to avoid blocking the event loop.

    Use this to wrap ``db.*`` function calls inside ``async def`` FastAPI endpoints::

        from api.dependencies import sync_to_async
        import core.db as database

        @router.get("/vehicles")
        async def list_vehicles(user=Depends(get_current_user)):
            vehicles = await sync_to_async(database.get_vehicles_for_user, user["id"])
            return vehicles
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
