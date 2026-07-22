"""
Session token management for Streamlit auth.

Replaces bare ``st.session_state`` with database-backed sessions that
have configurable expiry (default 8-hour TTL), server-side invalidation,
token rotation, and IP logging.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc
from typing import Any

from core.config import MAX_REFRESH_COUNT, SECRET_KEY, SESSION_TTL_HOURS
from core.logger import get_logger

log = get_logger("session")


def _hash_token(token: str) -> str:
    """Return a SHA-256 hash of the token salted with the secret key."""
    return hashlib.sha256(f"{SECRET_KEY}:{token}".encode()).hexdigest()


def _parse_expires(expires_at: datetime) -> datetime:
    """Normalize a datetime to a naive UTC datetime for comparison."""
    if expires_at.tzinfo is not None:
        return expires_at.replace(tzinfo=None)
    return expires_at


def create_session(user_id: int, ip_address: str | None = None) -> str:
    """
    Create a new session token for a user.

    The plain token is returned to the caller (to store in
    ``st.session_state``); only a hash is persisted in the database.

    Each session is assigned a unique JTI (JWT ID) for blocklist tracking.

    Args:
        user_id: User ID to create a session for.
        ip_address: Optional IP address of the client for audit.

    Returns:
        The plain-text session token (store this in the client).
    """
    import core.db as database

    plain = secrets.token_urlsafe(48)
    token_hash = _hash_token(plain)
    session_jti = str(uuid.uuid4())
    expires = datetime.now(UTC) + timedelta(hours=SESSION_TTL_HOURS)

    db_session = database.get_session()
    try:
        db_entry = database.Session(
            user_id=user_id,
            token_hash=token_hash,
            jti=session_jti,
            ip_address=ip_address,
            expires_at=expires,
        )
        db_session.add(db_entry)
        db_session.commit()
    except Exception:
        db_session.rollback()
        log.exception("Failed to create session for user %s", user_id)
        raise
    finally:
        db_session.close()

    log.info(
        "Session created for user %s (jti=%s, expires=%s)",
        user_id,
        session_jti[:16],
        expires,
    )
    return plain


def validate_session(token: str) -> dict[str, Any] | None:
    """
    Validate a session token and return user info.

    Checks:
    1. Token exists in the database (by hash lookup).
    2. Session is not revoked (``is_revoked`` flag).
    3. Session has not expired.

    Args:
        token: The plain-text session token.

    Returns:
        Dict with user info (``id``, ``username``, ``role``, ``organization_id``,
        ``name``, ``email``) or ``None`` if the token is invalid, expired, or revoked.
    """
    import core.db as database

    token_hash = _hash_token(token)

    db_session = database.get_session()
    try:
        db_entry = (
            db_session.query(database.Session)
            .filter_by(
                token_hash=token_hash,
            )
            .first()
        )

        if not db_entry:
            return None

        # Check if revoked
        if db_entry.is_revoked:
            log.info("Session %d is revoked", db_entry.id)
            return None

        # Check expiry
        expires_naive = _parse_expires(db_entry.expires_at)
        now_naive = datetime.now(UTC).replace(tzinfo=None)

        if expires_naive < now_naive:
            log.info("Session %s expired", db_entry.id)
            db_session.delete(db_entry)
            db_session.commit()
            return None

        # Get user info
        user = (
            db_session.query(database.User)
            .filter_by(
                id=db_entry.user_id,
            )
            .first()
        )
        if not user:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role or "driver",
            "organization_id": user.organization_id,
            "name": user.name,
            "email": user.email,
            "auth_method": "session",
            "jti": db_entry.jti,
            "session_id": db_entry.id,
        }
    finally:
        db_session.close()


def invalidate_session(token: str) -> None:
    """Delete a session token (logout)."""
    import core.db as database

    token_hash = _hash_token(token)

    db_session = database.get_session()
    try:
        db_entry = (
            db_session.query(database.Session)
            .filter_by(
                token_hash=token_hash,
            )
            .first()
        )
        if db_entry:
            db_session.delete(db_entry)
            db_session.commit()
            log.info("Session %d invalidated (logout)", db_entry.id)
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


def refresh_session(token: str) -> tuple[str, str] | None:
    """
    Rotate a session token: creates a new token and invalidates the old one.

    This implements **token rotation** as a security measure.  Each refresh
    increments the session's ``refresh_count``.  Once ``MAX_REFRESH_COUNT``
    is reached, the user must re-authenticate.

    Args:
        token: The current plain-text session token.

    Returns:
        A tuple of ``(new_token, old_token)`` on success, or ``None`` if the
        current token is invalid, expired, revoked, or has exceeded the maximum
        refresh count.
    """
    import core.db as database

    token_hash = _hash_token(token)
    now = datetime.now(UTC)
    now_naive = now.replace(tzinfo=None)

    db_session = database.get_session()
    try:
        db_entry = (
            db_session.query(database.Session)
            .filter_by(
                token_hash=token_hash,
            )
            .first()
        )

        if not db_entry:
            log.warning("Refresh failed: session not found")
            return None

        # Check revocation
        if db_entry.is_revoked:
            log.warning("Refresh failed: session %d is revoked", db_entry.id)
            return None

        # Check expiry
        expires_naive = _parse_expires(db_entry.expires_at)
        if expires_naive < now_naive:
            log.warning("Refresh failed: session %d expired", db_entry.id)
            db_session.delete(db_entry)
            db_session.commit()
            return None

        # Check refresh limit
        current_count = db_entry.refresh_count or 0
        if current_count >= MAX_REFRESH_COUNT:
            log.warning(
                "Refresh failed: session %d exceeded max refresh count (%d)",
                db_entry.id,
                MAX_REFRESH_COUNT,
            )
            # Revoke the session to force re-authentication
            db_entry.is_revoked = True
            db_entry.revoked_at = now
            db_session.commit()
            return None

        # Generate new token and update the session row in place
        new_plain = secrets.token_urlsafe(48)
        new_hash = _hash_token(new_plain)
        new_jti = str(uuid.uuid4())
        new_expires = now + timedelta(hours=SESSION_TTL_HOURS)

        # Capture old JTI BEFORE overwriting it
        old_jti = db_entry.jti

        db_entry.token_hash = new_hash
        db_entry.jti = new_jti
        db_entry.expires_at = new_expires
        db_entry.refresh_count = current_count + 1

        db_session.commit()

        log.info(
            "Session %d refreshed (count=%d, old_jti=%s, new_jti=%s)",
            db_entry.id,
            current_count + 1,
            old_jti[:16] if old_jti else "none",
            new_jti[:16],
        )

        return new_plain, token
    except Exception:
        db_session.rollback()
        log.exception("Failed to refresh session")
        return None
    finally:
        db_session.close()


def revoke_session(token: str) -> bool:
    """
    Revoke a session token immediately.

    Marks the session as revoked in the database and attempts to add its JTI
    to the Redis blocklist for instant rejection.  The session row is kept
    (soft-delete) for audit purposes.

    Args:
        token: The plain-text session token to revoke.

    Returns:
        ``True`` if the session was found and revoked, ``False`` otherwise.
    """
    import core.db as database

    token_hash = _hash_token(token)
    now = datetime.now(UTC)

    db_session = database.get_session()
    try:
        db_entry = (
            db_session.query(database.Session)
            .filter_by(
                token_hash=token_hash,
            )
            .first()
        )

        if not db_entry:
            log.warning("Revoke failed: session not found")
            return False

        db_entry.is_revoked = True
        db_entry.revoked_at = now
        db_session.commit()

        log.info("Session %d revoked", db_entry.id)

        # Try to add to Redis blocklist (non-blocking best-effort)
        jti = db_entry.jti
        if jti:
            try:
                import asyncio

                from auth.token_blocklist import add_to_blocklist

                ttl = int(
                    (db_entry.expires_at - now).total_seconds()
                    if db_entry.expires_at
                    else SESSION_TTL_HOURS * 3600
                )
                # Attempt async add — if no event loop is running, that's OK
                try:
                    asyncio.get_running_loop()
                    # We're in an async context, schedule it
                    import asyncio

                    asyncio.ensure_future(add_to_blocklist(jti, expires_in=ttl))
                except RuntimeError:
                    # No running event loop (synchronous context)
                    pass
            except Exception:
                log.debug("Could not add revoked JTI to blocklist")

        return True
    except Exception:
        db_session.rollback()
        log.exception("Failed to revoke session")
        return False
    finally:
        db_session.close()
