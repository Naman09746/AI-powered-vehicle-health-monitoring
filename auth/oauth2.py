"""
OAuth2 / OpenID Connect support with Keycloak.

Provides JWT token validation against Keycloak's JWKS endpoint,
supporting both RS256-signed tokens and standard OIDC claims.

Usage::

    from auth.oauth2 import verify_oauth2_token, get_current_user_oauth2
    user = await get_current_user_oauth2(token)
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any
from urllib.request import Request, urlopen

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import KEYCLOAK_CLIENT_ID, KEYCLOAK_REALM, KEYCLOAK_URL, OAUTH_ENABLED
from core.logger import get_logger

log = get_logger("oauth2")

bearer_scheme = HTTPBearer(auto_error=False)

# ── JWKS cache ───────────────────────────────────────────────────

_jwks_cache: dict[str, Any] | None = None
_jwks_cache_ts: float = 0.0
_JWKS_CACHE_TTL: int = 3600  # Re-fetch every hour


def _build_well_known_url() -> str:
    """Construct the OpenID Configuration discovery URL for the realm."""
    return f"{KEYCLOAK_URL.rstrip('/')}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"


def _build_jwks_url() -> str:
    """Construct the JWKS certificate URL for the realm."""
    return f"{KEYCLOAK_URL.rstrip('/')}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"


def _fetch_json(url: str, timeout: int = 10) -> dict[str, Any] | None:
    """Fetch JSON from a URL with a timeout. Returns None on failure."""
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log.warning("Failed to fetch %s: %s", url, exc)
        return None


def _get_jwks() -> dict[str, Any] | None:
    """Get cached JWKS, fetching from Keycloak if stale or absent."""
    global _jwks_cache, _jwks_cache_ts  # noqa: PLW0603

    now = time.time()
    if _jwks_cache is not None and (now - _jwks_cache_ts) < _JWKS_CACHE_TTL:
        return _jwks_cache

    # Try discovery URL first to get the JWKS URI dynamically
    discovery = _fetch_json(_build_well_known_url())
    jwks_uri = None
    if discovery and "jwks_uri" in discovery:
        jwks_uri = discovery["jwks_uri"]
        log.info("Discovered JWKS URI: %s", jwks_uri)

    if not jwks_uri:
        jwks_uri = _build_jwks_url()

    jwks_data = _fetch_json(jwks_uri)
    if jwks_data and "keys" in jwks_data:
        _jwks_cache = jwks_data
        _jwks_cache_ts = now
        log.info("JWKS refreshed (%d keys)", len(jwks_data["keys"]))
        return _jwks_cache

    log.warning("JWKS fetch failed, returning stale cache")
    return _jwks_cache


def _find_jwk(kid: str) -> dict[str, Any] | None:
    """Find a JWK by its ``kid`` (key ID) in the cached JWKS set."""
    jwks = _get_jwks()
    if not jwks:
        return None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def _verify_rs256(token: str, jwk: dict[str, Any]) -> dict[str, Any] | None:
    """Verify an RS256-signed JWT using a JWK and return the decoded payload.

    Uses the ``jose`` library to construct an RSA public key from the JWK
    components and verify the token signature.
    """
    try:
        from jose import jwk as jose_jwk
        from jose import jws
        from jose.constants import Algorithms

        # Build the RSA public key from JWK components
        rsa_key = jose_jwk.construct(jwk, algorithm=Algorithms.RS256)

        # Verify and decode the JWT
        payload = jws.verify(token, rsa_key, algorithms=[Algorithms.RS256])
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)
    except Exception as exc:
        log.warning("RS256 verification failed: %s", exc)
        return None


def _verify_hs256(token: str, client_secret: str) -> dict[str, Any] | None:
    """Verify an HS256-signed JWT using the client secret."""
    try:
        from jose import jwt

        payload = jwt.decode(
            token,
            client_secret,
            algorithms=["HS256"],
            audience=KEYCLOAK_CLIENT_ID,
        )
        return payload
    except Exception as exc:
        log.warning("HS256 verification failed: %s", exc)
        return None


def verify_oauth2_token(token: str) -> dict[str, Any] | None:
    """Validate an OAuth2 / OIDC token against Keycloak's JWKS.

    Supports both RS256 (asymmetric, via JWKS) and HS256 (symmetric, via
    client secret) token signatures.  Verifies standard claims:
    ``exp``, ``iss``, ``aud``, ``azp``.

    Args:
        token: The raw JWT string (Bearer token) from the Authorization header.

    Returns:
        A dict with decoded claims (``sub``, ``preferred_username``, ``email``,
        ``realm_roles``, etc.) or ``None`` if validation fails.
    """
    if not OAUTH_ENABLED:
        log.debug("OAuth2 is disabled; skipping token validation")
        return None

    # Decode the JWT header without verification to get the algorithm and kid
    try:
        from jose import jws

        unverified_header = jws.get_unverified_header(token)
    except Exception as exc:
        log.warning("Failed to decode JWT header: %s", exc)
        return None

    algorithm = unverified_header.get("alg", "RS256")
    kid = unverified_header.get("kid")

    payload: dict[str, Any] | None = None

    if algorithm == "RS256" and kid:
        jwk = _find_jwk(kid)
        if not jwk:
            log.warning("JWK not found for kid=%s", kid)
            return None
        payload = _verify_rs256(token, jwk)
    elif algorithm == "HS256":
        from core.config import KEYCLOAK_CLIENT_SECRET

        if not KEYCLOAK_CLIENT_SECRET:
            log.warning(
                "HS256 token received but KEYCLOAK_CLIENT_SECRET is not configured"
            )
            return None
        payload = _verify_hs256(token, KEYCLOAK_CLIENT_SECRET)
    else:
        log.warning("Unsupported algorithm: %s", algorithm)
        return None

    if not payload:
        return None

    # ── Standard claim validation ──
    now = time.time()

    # exp (Expiration Time)
    exp = payload.get("exp")
    if exp and exp < now:
        log.warning("OAuth2 token expired (exp=%d)", exp)
        return None

    # nbf (Not Before)
    nbf = payload.get("nbf")
    if nbf and nbf > now:
        log.warning("OAuth2 token not yet valid (nbf=%d)", nbf)
        return None

    # iss (Issuer) — check that it matches our realm
    expected_iss = f"{KEYCLOAK_URL.rstrip('/')}/realms/{KEYCLOAK_REALM}"
    iss = payload.get("iss")
    if iss and iss != expected_iss:
        log.warning(
            "OAuth2 token issuer mismatch: expected %s, got %s", expected_iss, iss
        )
        return None

    # aud (Audience) — check that our client is in the audience
    aud = payload.get("aud")
    if aud and isinstance(aud, str) and aud != KEYCLOAK_CLIENT_ID:
        log.warning(
            "OAuth2 token audience mismatch: expected %s, got %s",
            KEYCLOAK_CLIENT_ID,
            aud,
        )
        return None
    if aud and isinstance(aud, list) and KEYCLOAK_CLIENT_ID not in aud:
        log.warning(
            "OAuth2 token audience mismatch: %s not in %s", KEYCLOAK_CLIENT_ID, aud
        )
        return None

    # azp (Authorized Party) — optional additional check
    azp = payload.get("azp")
    if azp and azp != KEYCLOAK_CLIENT_ID and KEYCLOAK_CLIENT_ID not in (aud or []):
        log.warning("OAuth2 token authorized party mismatch: %s", azp)
        return None

    log.info("OAuth2 token validated for subject=%s", payload.get("sub"))
    return payload


def oauth2_to_user_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a Keycloak JWT payload to the standard user info dict.

    Maps Keycloak claims to the dict format expected by the rest of the
    application (matching the return value of ``auth.session.validate_session``).
    """
    # Determine role from Keycloak realm roles
    realm_roles = payload.get("realm_roles", []) or []
    if payload.get("realm_access"):
        realm_roles = payload["realm_access"].get("roles", [])

    # Map Keycloak roles to application roles
    role = "driver"
    if "admin" in realm_roles:
        role = "admin"
    elif "fleet_manager" in realm_roles:
        role = "fleet_manager"
    elif "technician" in realm_roles:
        role = "technician"

    return {
        "id": int(payload.get("sub", 0)),  # Keycloak sub as user ID
        "username": payload.get("preferred_username", ""),
        "role": role,
        "organization_id": payload.get("organization_id"),
        "name": payload.get("name", payload.get("given_name", "")),
        "email": payload.get("email", ""),
        "auth_method": "oauth2",
        "jti": payload.get("jti", str(uuid.uuid4())),
    }


async def get_current_user_oauth2(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any] | None:
    """FastAPI dependency that validates an OAuth2 Bearer token via Keycloak.

    Returns the user info dict if validation succeeds, or ``None`` if OAuth2
    is disabled or the token is invalid.

    This dependency is designed to be called as the first step in
    ``get_current_user()`` in ``api/dependencies.py``, falling back to
    session tokens if OAuth2 validation returns ``None``.
    """
    if not OAUTH_ENABLED:
        return None

    if credentials is None:
        return None

    payload = verify_oauth2_token(credentials.credentials)
    if payload is None:
        return None

    # Check token blocklist
    jti = payload.get("jti")
    if jti:
        from auth.token_blocklist import is_blocklisted

        if await is_blocklisted(jti):
            log.warning("OAuth2 token JTI %s is blocklisted", jti)
            return None

    return oauth2_to_user_dict(payload)
