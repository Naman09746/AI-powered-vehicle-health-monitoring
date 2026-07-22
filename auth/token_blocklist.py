"""
Redis-backed token blocklist for instant session and JWT revocation.

Provides both async and sync interfaces.  When Redis is unavailable, falls
back to an in-memory cache and database-backed checks for persistence.

Usage::

    from auth.token_blocklist import add_to_blocklist, is_blocklisted

    await add_to_blocklist(jti, expires_in=3600)
    if await is_blocklisted(jti):
        raise HTTPException(status_code=401, detail="Token revoked")
"""

from __future__ import annotations

import contextlib
import hashlib
import time
from datetime import UTC
from typing import Any

from core.config import REDIS_URL, SECRET_KEY, SESSION_TTL_HOURS
from core.logger import get_logger

log = get_logger("token_blocklist")

# ── In-memory fallback cache ─────────────────────────────────────
# Used when Redis is unreachable; entries are best-effort and lost
# on process restart.
_blocklist_cache: dict[str, float] = {}  # jti -> expiry timestamp


def _blocklist_redis_key(jti: str) -> str:
    """Return the Redis key for a blocklist entry."""
    return f"token_blocklist:{jti}"


async def _get_redis_client() -> Any | None:
    """Create a short-lived async Redis connection.

    Returns the client if Redis is reachable, or ``None`` to signal that
    callers should use the fallback path.
    """
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            REDIS_URL,
            socket_connect_timeout=2,
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception:
        log.debug("Redis not available for token blocklist")
        return None


def _compute_expires_in(expires_at: int | None = None) -> int:
    """Compute the TTL in seconds for a blocklist entry.

    Falls back to the default session TTL if no explicit expiry is given.
    """
    if expires_at:
        ttl = expires_at - int(time.time())
        if ttl > 0:
            return ttl
    return int(SESSION_TTL_HOURS * 3600)


# ── Public API ───────────────────────────────────────────────────


async def add_to_blocklist(jti: str, expires_in: int | None = None) -> None:
    """Add a token JTI to the blocklist.

    The blocklist entry auto-expires after ``expires_in`` seconds (defaults to
    the configured ``SESSION_TTL_HOURS``).

    Tries Redis first; falls back to in-memory cache on failure.
    """
    ttl = _compute_expires_in(expires_in)
    redis = await _get_redis_client()

    if redis is not None:
        try:
            await redis.setex(_blocklist_redis_key(jti), ttl, "1")
            log.info("Token JTI %s added to Redis blocklist (ttl=%ds)", jti[:16], ttl)
            await redis.aclose()
            return
        except Exception:
            log.warning("Failed to add to Redis blocklist, falling back to cache")
        finally:
            with contextlib.suppress(Exception):
                await redis.aclose()

    # Fallback: in-memory cache
    _blocklist_cache[jti] = time.time() + ttl
    log.info("Token JTI %s added to in-memory blocklist (ttl=%ds)", jti[:16], ttl)

    # Also record in the database for durability across restarts
    _persist_blocklist_entry(jti, ttl)


async def is_blocklisted(jti: str) -> bool:
    """Check whether a token JTI has been blocklisted.

    Checks in order:
    1. In-memory cache (fastest)
    2. Redis
    3. Database fallback (slowest)
    """
    # 1. In-memory cache (fast path)
    expiry = _blocklist_cache.get(jti)
    if expiry is not None:
        if time.time() < expiry:
            return True
        # Expired entry — clean up
        del _blocklist_cache[jti]
        return False

    # 2. Redis
    redis = await _get_redis_client()
    if redis is not None:
        try:
            result = await redis.get(_blocklist_redis_key(jti))
            await redis.aclose()
            return result is not None
        except Exception:
            log.warning("Redis blocklist check failed, trying DB")
        finally:
            with contextlib.suppress(Exception):
                await redis.aclose()

    # 3. Database fallback
    return _db_is_blocklisted(jti)


# ── Database fallback ────────────────────────────────────────────


def _db_is_blocklisted(jti: str) -> bool:
    """Check the database for a blocklisted JTI.

    Looks up the session by JTI and checks the ``is_revoked`` flag.
    """
    import core.db as database

    session = database.get_session()
    try:
        db_session = session.query(database.Session).filter_by(jti=jti).first()
        return bool(db_session and db_session.is_revoked)
    except Exception:
        log.exception("DB blocklist check failed")
        return False  # Fail open — treat as not blocklisted
    finally:
        session.close()


def _persist_blocklist_entry(jti: str, ttl_seconds: int) -> None:
    """Record a revocation in the database for durability across restarts.

    Updates the session record's ``is_revoked`` flag if the JTI corresponds
    to an existing session.
    """
    from datetime import datetime

    import core.db as database

    session = database.get_session()
    try:
        db_session = session.query(database.Session).filter_by(jti=jti).first()
        if db_session:
            db_session.is_revoked = True
            db_session.revoked_at = datetime.now(UTC)
            session.commit()
            log.info("Session %d marked as revoked in DB", db_session.id)
    except Exception:
        session.rollback()
        log.exception("Failed to persist blocklist entry")
    finally:
        session.close()


def compute_token_jti(token: str) -> str:
    """Derive a deterministic JTI from a session token for blocklist usage.

    Uses a SHA-256 hash of the token (prefixed with the secret key) so that
    the same token always produces the same JTI.
    """
    return hashlib.sha256(f"{SECRET_KEY}:blocklist:{token}".encode()).hexdigest()
