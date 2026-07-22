"""
Authentication router — login, register, logout, token refresh, and revocation.
"""

from __future__ import annotations

from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

import core.db as database
from api.dependencies import get_current_user
from api.schemas.vehicle import (
    LoginRequest,
    LoginResponse,
    RefreshTokenResponse,
    RegisterRequest,
    RevokeTokenRequest,
    RevokeTokenResponse,
    StatusResponse,
)
from auth.session import (
    create_session,
    invalidate_session,
    refresh_session,
    revoke_session,
)
from core.config import MAX_REFRESH_COUNT
from core.logger import get_logger

log = get_logger("auth.router")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _extract_bearer_token(request: Request) -> str | None:
    """Extract the Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request):
    """Authenticate with username + password, receive a session token."""
    user = database.authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Capture client IP if available
    ip_address = request.client.host if request.client else None
    token = create_session(user.id, ip_address=ip_address)

    return LoginResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        role=user.role or "driver",
        name=user.name,
    )


@router.post("/register", response_model=StatusResponse)
async def register(body: RegisterRequest):
    """Register a new user account."""
    user = database.create_user(
        username=body.username,
        password=body.password,
        name=body.name,
        email=body.email,
        phone=body.phone,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    return StatusResponse(status="ok", detail=f"User '{user.username}' created")


@router.post("/logout", response_model=StatusResponse)
async def logout(request: Request, user: dict[str, Any] = Depends(get_current_user)):
    """Invalidate the current session token (logout)."""
    token = _extract_bearer_token(request)
    if token:
        invalidate_session(token)
        log.info("User %s logged out (session invalidated)", user.get("id"))
    return StatusResponse(status="ok", detail="Logged out")


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh(request: Request, user: dict[str, Any] = Depends(get_current_user)):
    """Rotate the current session token, returning a new one.

    Token rotation invalidates the old token and creates a new one with
    a fresh expiry.  The refresh count is incremented; once the maximum
    is reached, the session is revoked and the user must re-authenticate.

    This endpoint requires a valid session token (OAuth2 tokens cannot
    be refreshed via this endpoint — they are refreshed through Keycloak).
    """
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Bearer token in Authorization header",
        )

    # Only session tokens can be refreshed via this endpoint
    if user.get("auth_method") == "oauth2":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth2 tokens cannot be refreshed via this endpoint; "
            "use the Keycloak token endpoint",
        )

    result = refresh_session(token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed — session may be expired, revoked, "
            "or exceeded maximum refresh count",
        )

    new_token, _old_token = result

    # Get current refresh count from user info
    refresh_count = user.get("refresh_count", 0) + 1

    return RefreshTokenResponse(
        token=new_token,
        user_id=user["id"],
        username=user["username"],
        role=user.get("role", "driver"),
        name=user.get("name"),
        refresh_count=refresh_count,
        max_refresh_count=MAX_REFRESH_COUNT,
    )


@router.post("/revoke", response_model=StatusResponse)
async def revoke(
    request: Request,
    body: RevokeTokenRequest | None = None,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Revoke the current session token immediately.

    Unlike logout (which deletes the session), revocation marks the session
    as revoked and adds its JTI to the blocklist for instant rejection.
    The session record is retained for audit purposes.
    """
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Bearer token in Authorization header",
        )

    reason = body.reason if body else None
    success = revoke_session(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked",
        )

    log.info(
        "User %s revoked session (reason=%s)", user.get("id"), reason or "not specified"
    )
    return StatusResponse(
        status="ok",
        detail=f"Session revoked{f' ({reason})' if reason else ''}",
    )


@router.post("/revoke-all", response_model=RevokeTokenResponse)
async def revoke_all_sessions(user: dict[str, Any] = Depends(get_current_user)):
    """Revoke all sessions for the current user.

    This is useful when a user suspects their account has been compromised
    or wants to force logout from all devices.
    """
    from datetime import datetime

    import core.db as database

    db_session = database.get_session()
    try:
        sessions = (
            db_session.query(database.Session)
            .filter_by(
                user_id=user["id"],
                is_revoked=False,
            )
            .all()
        )

        now = datetime.now(UTC)
        count = 0
        for s in sessions:
            s.is_revoked = True
            s.revoked_at = now
            count += 1

        db_session.commit()

        log.info("Revoked %d sessions for user %s", count, user.get("id"))
        return RevokeTokenResponse(
            status="ok",
            detail=f"Revoked {count} active session(s)",
            revoked_sessions_count=count,
        )
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
