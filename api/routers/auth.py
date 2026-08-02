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
import uuid

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


from api.limiter import limiter


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest):

    """Authenticate with username + password, receive a session token."""
    try:
        user = database.authenticate_user(body.username, body.password)
    except Exception as e:
        log.error("Login DB error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {str(e)}",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    from api.routers.simulator import seed_demo_fleet_for_user
    try:
        seed_demo_fleet_for_user(user.id)
    except Exception:
        pass

    # Capture client IP if available
    ip_address = request.client.host if request.client else None
    token = create_session(user.id, ip_address=ip_address)

    from core.audit import log_audit_event
    log_audit_event(user.id, "user.login", resource_type="User", resource_id=user.id, details={"ip": ip_address})

    return LoginResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        role=user.role or "driver",
        name=user.name,
        onboarding_complete=getattr(user, "onboarding_complete", False) or False,
    )



@router.post("/complete-onboarding")
async def complete_onboarding(user: dict[str, Any] = Depends(get_current_user)):
    """Mark onboarding as complete for the logged-in user."""
    session = database.get_session()
    try:
        db_user = session.query(database.User).filter_by(id=user["id"]).first()
        if db_user:
            db_user.onboarding_complete = True
            session.commit()
        return {"status": "success", "onboarding_complete": True}
    finally:
        session.close()



@router.post("/register", response_model=StatusResponse)
async def register(body: RegisterRequest):
    """Register a new user account."""
    try:
        user = database.create_user(
            username=body.username,
            password=body.password,
            name=body.name,
            email=body.email,
            phone=body.phone,
        )
    except Exception as e:
        log.error("Registration DB error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
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


# ── Email Verification & Password Reset ───────────────────────

@router.get("/verify-email")
async def verify_email(token: str):
    """Verify user email address using token from email link."""
    db_session = database.get_session()
    try:
        user = db_session.query(database.User).filter_by(email_verify_token=token).first()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")

        user.email_verified = True
        user.email_verify_token = None
        db_session.commit()
        return {"status": "success", "message": "Email verified successfully"}
    finally:
        db_session.close()


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, body: dict):
    """Request password reset link. Sends email if account exists."""
    email = body.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    db_session = database.get_session()
    try:
        user = db_session.query(database.User).filter_by(email=email).first()
        if user:
            import uuid, datetime
            token = str(uuid.uuid4())
            user.reset_token = token
            user.reset_token_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            db_session.commit()

            from core.email import send_password_reset_email
            send_password_reset_email(email, token)

        return {"status": "success", "message": "If that email exists, a reset link has been sent."}
    finally:
        db_session.close()


@router.post("/reset-password")
async def reset_password(body: dict):
    """Reset password using reset token."""
    token = body.get("token")
    new_password = body.get("new_password")

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token and new_password are required")

    db_session = database.get_session()
    try:
        user = db_session.query(database.User).filter_by(reset_token=token).first()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        import bcrypt
        user.password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user.reset_token = None
        user.reset_token_expiry = None
        db_session.commit()

        return {"status": "success", "message": "Password reset successful. Please sign in with your new password."}
    finally:
        db_session.close()


# ── Google OAuth & MFA/TOTP ───────────────────────────────────

@router.post("/oauth/google")
async def google_oauth(request: Request, body: dict):
    """Authenticate or register user via Google OAuth credential token."""
    credential = body.get("credential")
    if not credential:
        raise HTTPException(status_code=400, detail="Google credential token missing")

    # Decode Google JWT payload to extract real user email & name
    payload = {}
    try:
        import json, base64
        parts = credential.split(".")
        if len(parts) >= 2:
            p_b64 = parts[1]
            rem = len(p_b64) % 4
            if rem > 0:
                p_b64 += "=" * (4 - rem)
            payload = json.loads(base64.urlsafe_b64decode(p_b64.encode("utf-8")).decode("utf-8"))
            log.info("Successfully decoded Google OAuth JWT for email: %s", payload.get("email"))
    except Exception as e:
        log.warning("Could not decode Google JWT payload: %s", e)

    email = payload.get("email") or body.get("email") or f"google_{uuid.uuid4().hex[:8]}@example.com"
    name = payload.get("name") or body.get("name") or "Google User"

    db_session = database.get_session()
    try:
        user = db_session.query(database.User).filter_by(email=email).first()
        if not user:
            # Create user for social sign-in
            import bcrypt
            random_pw = uuid.uuid4().hex
            pw_hash = bcrypt.hashpw(random_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            base_user = email.split("@")[0].replace(".", "_").replace("+", "_")
            user = database.User(
                username=base_user + "_" + uuid.uuid4().hex[:4],
                password_hash=pw_hash,
                email=email,
                name=name,
                email_verified=True,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        from api.routers.simulator import seed_demo_fleet_for_user
        try:
            seed_demo_fleet_for_user(user.id)
        except Exception as se:
            log.warning("Fleet seed warning: %s", se)

        ip_address = request.client.host if request.client else None
        token = create_session(user.id, ip_address=ip_address)

        try:
            from core.audit import log_audit_event
            log_audit_event(user.id, "user.oauth_login", resource_type="User", resource_id=user.id)
        except Exception:
            pass

        return {
            "token": token,
            "access_token": token,
            "user_id": user.id,
            "username": user.username,
            "role": getattr(user, "role", "driver") or "driver",
            "name": user.name,
            "onboarding_complete": getattr(user, "onboarding_complete", False) or False,
            "user": {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "role": getattr(user, "role", "driver") or "driver",
            },
        }
    except Exception as err:
        db_session.rollback()
        log.error("Google OAuth execution error: %s", err, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Google sign-in error: {str(err)}")
    finally:
        db_session.close()


@router.post("/mfa/setup")
async def mfa_setup(user: dict[str, Any] = Depends(get_current_user)):
    """Generate TOTP secret key for Multi-Factor Authentication."""
    try:
        import pyotp
        secret = pyotp.random_base32()
        otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.get("username", "user"),
            issuer_name="VehicleHealthMonitor",
        )
        return {"status": "success", "secret": secret, "otpauth_url": otpauth_url}
    except ImportError:
        return {"status": "error", "message": "pyotp library not installed"}


@router.post("/mfa/verify")
async def mfa_verify(body: dict, user: dict[str, Any] = Depends(get_current_user)):
    """Verify TOTP code and activate MFA."""
    code = body.get("code")
    secret = body.get("secret")

    if not code or not secret:
        raise HTTPException(status_code=400, detail="Code and secret are required")

    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        if not totp.verify(code):
            raise HTTPException(status_code=400, detail="Invalid 6-digit TOTP code")

        db_session = database.get_session()
        try:
            db_user = db_session.query(database.User).filter_by(id=user["id"]).first()
            if db_user:
                db_user.totp_secret = secret
                db_user.totp_enabled = True
                db_session.commit()
            return {"status": "success", "message": "MFA enabled successfully"}
        finally:
            db_session.close()
    except ImportError:
        raise HTTPException(status_code=500, detail="pyotp not installed")

