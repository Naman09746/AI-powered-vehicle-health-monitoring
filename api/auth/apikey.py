"""
API Key authentication for machine-to-machine communication.

Used by:
- MQTT sensor data ingestion
- Fleet simulators
- External integrations
- CI/CD pipelines
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from core.logger import get_logger

log = get_logger("api.auth.apikey")

# Header name for API keys
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKey:
    """API Key model stored in database."""

    def __init__(
        self,
        id: int,
        user_id: int,
        name: str,
        key_hash: str,
        prefix: str,
        scopes: list[str],
        expires_at: datetime | None,
        last_used_at: datetime | None,
        created_at: datetime,
        is_active: bool,
    ):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.key_hash = key_hash
        self.prefix = prefix
        self.scopes = scopes
        self.expires_at = expires_at
        self.last_used_at = last_used_at
        self.created_at = created_at
        self.is_active = is_active

    def has_scope(self, scope: str) -> bool:
        """Check if key has required scope."""
        return scope in self.scopes or "admin" in self.scopes


def hash_api_key(prefix: str, key: str) -> str:
    """Hash API key for storage."""
    return hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key with prefix.

    Returns:
        (full_key, prefix) where full_key is the key to give to user,
        and prefix is the short identifier stored for display.
    """
    prefix = f"vhm_{secrets.token_urlsafe(8)}"
    key = secrets.token_urlsafe(32)
    return f"{prefix}.{key}", prefix


async def validate_api_key(
    api_key: str | None = Depends(API_KEY_HEADER),
) -> APIKey | None:
    """
    Validate API key from X-API-Key header.

    Returns APIKey object if valid, raises HTTPException if invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key (X-API-Key header)",
        )

    # Parse prefix.key format
    try:
        prefix, key = api_key.split(".", 1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    # Look up by prefix
    import core.db as database

    session = database.get_session()
    try:
        from core.db import APIKey as APIKeyModel

        key_hash = hash_api_key(prefix, key)
        db_key = (
            session.query(APIKeyModel)
            .filter_by(prefix=prefix, key_hash=key_hash)
            .first()
        )

        if not db_key:
            log.warning("Invalid API key attempted: prefix=%s", prefix)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        # Check active
        if not db_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key disabled",
            )

        # Check expiry
        if db_key.expires_at:
            expires = db_key.expires_at
            if expires.tzinfo is not None:
                expires = expires.replace(tzinfo=None)
            if expires < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key expired",
                )

        # Update last used
        db_key.last_used_at = datetime.utcnow()
        session.commit()

        return APIKey(
            id=db_key.id,
            user_id=db_key.user_id,
            name=db_key.name,
            key_hash=db_key.key_hash,
            prefix=db_key.prefix,
            scopes=db_key.scopes,
            expires_at=db_key.expires_at,
            last_used_at=db_key.last_used_at,
            created_at=db_key.created_at,
            is_active=db_key.is_active,
        )
    finally:
        session.close()


async def get_current_user_from_api_key(
    api_key: APIKey = Depends(validate_api_key),
) -> dict[str, Any]:
    """Get user info from validated API key."""
    import core.db as database

    session = database.get_session()
    try:
        user = session.query(database.User).filter_by(id=api_key.user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "organization_id": user.organization_id,
            "name": user.name,
            "email": user.email,
            "api_key_id": api_key.id,
            "api_key_scopes": api_key.scopes,
        }
    finally:
        session.close()


def require_scope(scope: str):
    """Dependency factory to require a specific API key scope."""

    async def check_scope(user: dict = Depends(get_current_user_from_api_key)) -> dict:
        scopes = user.get("api_key_scopes", [])
        if scope not in scopes and "admin" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope: {scope}",
            )
        return user

    return check_scope
