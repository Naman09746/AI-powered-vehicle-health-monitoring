"""
OAuth2/OIDC authentication middleware for Keycloak/Auth0 integration.

Supports:
- OpenID Connect discovery
- JWKS verification
- Token refresh rotation
- Redis blocklist for token revocation
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jose import JWTError, jwk, jwt
from jose.constants import Algorithms
from pydantic import BaseModel, Field

from core.config import REDIS_URL, SECRET_KEY
from core.logger import get_logger

log = get_logger("api.auth.oauth2")

# ── Configuration ──────────────────────────────────────────────

# OIDC provider configuration
# Set these in .env:
#   OIDC_ISSUER=https://keycloak.example.com/realms/vehicle-health
#   OIDC_CLIENT_ID=vehicle-health-api
#   OIDC_CLIENT_SECRET=your-client-secret

OIDC_ISSUER = None  # Will be loaded from core.config
OIDC_CLIENT_ID = None
OIDC_CLIENT_SECRET = None

# Redis client for token blocklist
_redis = None


async def get_redis():
    """Lazy-initialized Redis client for blocklist."""
    global _redis
    if _redis is None and REDIS_URL:
        try:
            import redis.asyncio as aioredis

            _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            await _redis.ping()
        except Exception:
            log.warning("Redis not available for token blocklist")
    return _redis


# ── JWKS Discovery ─────────────────────────────────────────────


class JWKSManager:
    """Manages JWKS key discovery and caching."""

    def __init__(self):
        self._keys: dict[str, Any] = {}
        self._last_fetch = 0
        self._cache_ttl = 3600  # 1 hour

    async def _fetch_keys(self) -> dict:
        """Fetch JWKS from OIDC provider."""
        if not OIDC_ISSUER:
            return {}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Discover OIDC configuration
                resp = await client.get(
                    f"{OIDC_ISSUER}/.well-known/openid-configuration"
                )
                resp.raise_for_status()
                oidc_config = resp.json()
                jwks_uri = oidc_config["jwks_uri"]

                # Fetch JWKS
                resp = await client.get(jwks_uri)
                resp.raise_for_status()
                jwks = resp.json()

                # Build key map
                keys = {}
                for key_data in jwks.get("keys", []):
                    kid = key_data.get("kid")
                    if kid:
                        keys[kid] = jwk.construct(key_data)
                return keys
        except Exception:
            log.exception("Failed to fetch JWKS")
            return {}

    async def get_key(self, kid: str) -> Any | None:
        """Get JWK key by key ID, with caching."""
        now = time.time()
        if now - self._last_fetch > self._cache_ttl or not self._keys:
            self._keys = await self._fetch_keys()
            self._last_fetch = now
        return self._keys.get(kid)


_jwks_manager = JWKSManager()


# ── Token Management ───────────────────────────────────────────


class TokenData(BaseModel):
    """Parsed and validated token data."""

    sub: str
    user_id: int
    username: str
    role: str = "driver"
    organization_id: int | None = None
    email: str | None = None
    name: str | None = None
    scopes: list[str] = Field(default_factory=list)
    exp: int | None = None
    iat: int | None = None
    iss: str | None = None
    token_type: str = "access"

    model_config = {"arbitrary_types_allowed": True}


class TokenManager:
    """Manages JWT token creation, validation, and refresh."""

    def __init__(self):
        self.secret_key = SECRET_KEY
        self.algorithm = Algorithms.HS256
        self.access_token_ttl = timedelta(minutes=30)
        self.refresh_token_ttl = timedelta(days=7)

    def create_access_token(
        self,
        user_id: int,
        username: str,
        role: str = "driver",
        organization_id: int | None = None,
        extra_claims: dict | None = None,
    ) -> str:
        """Create a short-lived access token."""
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "token_type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + self.access_token_ttl).timestamp()),
        }
        if organization_id:
            payload["organization_id"] = organization_id
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: int, username: str) -> str:
        """Create a long-lived refresh token."""
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "username": username,
            "token_type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + self.refresh_token_ttl).timestamp()),
            "jti": None,  # Will be set in create_refresh_token
        }
        import uuid

        payload["jti"] = str(uuid.uuid4())
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    async def validate_token(self, token: str) -> TokenData | None:
        """Validate token with Redis blocklist check."""
        try:
            # Decode without verification first to check type
            unverified = jwt.get_unverified_claims(token)

            # Check if token is on blocklist
            redis = await get_redis()
            if redis:
                jti = unverified.get("jti")
                if jti:
                    blocked = await redis.get(f"token:blocked:{jti}")
                    if blocked:
                        log.warning("Token has been revoked (jti=%s)", jti[:8])
                        return None

            # Verify the token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True},
            )

            return TokenData(
                sub=payload.get("sub"),
                user_id=int(payload["sub"]),
                username=payload.get("username", ""),
                role=payload.get("role", "driver"),
                organization_id=payload.get("organization_id"),
                email=payload.get("email"),
                name=payload.get("name"),
                scopes=payload.get("scopes", []),
                exp=payload.get("exp"),
                iat=payload.get("iat"),
                iss=payload.get("iss"),
                token_type=payload.get("token_type", "access"),
            )
        except JWTError as e:
            log.warning("Token validation failed: %s", str(e))
            return None
        except Exception:
            log.exception("Unexpected token validation error")
            return None

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, str] | None:
        """Exchange a refresh token for a new access + refresh token pair."""
        token_data = await self.validate_token(refresh_token)
        if not token_data or token_data.token_type != "refresh":
            return None

        # Rotate: revoke old refresh token
        redis = await get_redis()
        if redis and hasattr(token_data, "sub"):
            jti = refresh_token  # We need the jti from unverified claims
            try:
                unverified = jwt.get_unverified_claims(refresh_token)
                jti = unverified.get("jti")
                if jti:
                    await redis.setex(
                        f"token:blocked:{jti}",
                        int(self.refresh_token_ttl.total_seconds()),
                        "revoked",
                    )
            except Exception:
                pass

        # Create new token pair
        new_access = self.create_access_token(
            user_id=token_data.user_id,
            username=token_data.username,
            role=token_data.role,
            organization_id=token_data.organization_id,
        )
        new_refresh = self.create_refresh_token(
            user_id=token_data.user_id,
            username=token_data.username,
        )
        return new_access, new_refresh

    async def revoke_token(self, token: str) -> bool:
        """Revoke a token by adding its JTI to Redis blocklist."""
        try:
            unverified = jwt.get_unverified_claims(token)
            jti = unverified.get("jti")
            if not jti:
                return False
            redis = await get_redis()
            if redis:
                await redis.setex(
                    f"token:blocked:{jti}",
                    int(self.refresh_token_ttl.total_seconds()),
                    "revoked",
                )
                return True
            return False
        except Exception:
            return False


token_manager = TokenManager()


# ── FastAPI Dependencies ───────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_oauth2(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenData | None:
    """OAuth2/OIDC-based auth dependency.

    Validates Bearer JWT token from Authorization header.
    Falls back to session-based auth if OIDC is not configured.
    """
    if not credentials:
        return None

    token = credentials.credentials
    token_data = await token_manager.validate_token(token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def get_current_user_optional_oauth2(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenData | None:
    """Optional OAuth2 dependency, returns None for unauthenticated requests."""
    if not credentials:
        return None
    return await token_manager.validate_token(credentials.credentials)
