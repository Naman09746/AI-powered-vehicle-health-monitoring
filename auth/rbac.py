"""
Enhanced Role-Based Access Control (RBAC) with resource-level permissions.

Supports:
- Role hierarchy (driver < technician < fleet_manager < admin)
- Resource-level permission checks
- Organization-scoped access
- ABAC (Attribute-Based Access Control) policies via ``auth.abac``
- API key scope checking via ``require_scope``
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.logger import get_logger

log = get_logger("rbac")

bearer_scheme = HTTPBearer(auto_error=False)

# ── Permission sets per role ───────────────────────────────────
# Each role inherits all permissions from lower roles.

PERMISSIONS: dict[str, set[str]] = {
    "driver": {
        "vehicle:read:own",
        "alert:read:own",
        "prediction:read:own",
        "maintenance:read:own",
        "upload:create:own",
        "upload:read:own",
    },
    "technician": {
        "vehicle:read:any",
        "alert:read:any",
        "alert:acknowledge",
        "prediction:read:any",
        "prediction:run",
        "maintenance:read:any",
        "maintenance:update",
        "maintenance:create",
        "upload:read:any",
    },
    "fleet_manager": {
        "vehicle:create",
        "vehicle:update",
        "vehicle:delete",
        "alert:dismiss",
        "report:generate",
        "report:export",
        "fleet:read",
        "model:read",
        "model:train",
    },
    "admin": {
        "vehicle:read:all",
        "user:manage",
        "user:read",
        "user:update_role",
        "organization:manage",
        "model:delete",
        "model:promote",
        "model:rollback",
        "webhook:manage",
        "apikey:manage",
        "audit:read",
        "settings:manage",
    },
}

# ── Role hierarchy ─────────────────────────────────────────────
ROLE_HIERARCHY = ["driver", "technician", "fleet_manager", "admin"]

# ── Standard resource-level permissions (for ABAC integration) ─
RESOURCE_PERMISSIONS: set[str] = {
    "vehicle:read",
    "vehicle:write",
    "vehicle:create",
    "vehicle:update",
    "vehicle:delete",
    "model:train",
    "model:promote",
    "alert:dismiss",
    "report:generate",
    "admin:users",
}


def get_role_permissions(role: str) -> set[str]:
    """Get all permissions for a role, including inherited ones."""
    perms: set[str] = set()
    for r in ROLE_HIERARCHY:
        perms.update(PERMISSIONS.get(r, set()))
        if r == role:
            break
    else:
        return PERMISSIONS.get("driver", set()).copy()
    return perms


def has_permission(role: str | None, permission: str) -> bool:
    """Check if a role has a specific permission."""
    if not role:
        return False
    return permission in get_role_permissions(role)


def require_permission(permission: str) -> Callable:
    """
    FastAPI dependency that checks the current user has a specific permission.

    Uses the ABAC system for evaluation (which in turn falls back to RBAC).

    Usage::

        @router.get("/vehicles", dependencies=[Depends(require_permission("vehicle:read:own"))])
    """

    async def permission_checker(
        user: dict[str, Any] = Depends(lambda: None),
    ) -> dict[str, Any]:
        # Use the ABAC-aware permission checker
        from api.dependencies import get_current_user
        from auth.abac import check_permission as abac_check

        current_user = await get_current_user()

        if not abac_check(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires '{permission}'",
            )
        return current_user

    return permission_checker


def check_resource_access(
    user: dict[str, Any],
    permission: str,
    resource_user_id: int | None = None,
    resource_org_id: int | None = None,
) -> bool:
    """
    Check if user has access to a specific resource.

    Implements RBAC-style checks (not ABAC — this is the fallback called by
    ``auth.abac.check_permission`` after policy evaluation):
    - admins can access any resource
    - users can access their own resources with :own permissions
    - fleet managers can access any resource in their org
    """
    role = user.get("role", "driver")

    # Admin can access everything
    if role == "admin":
        return True

    # Check base permission
    if not has_permission(role, permission):
        return False

    # For :own permissions, check resource ownership
    if permission.endswith(":own"):
        if resource_user_id is not None:
            return user["id"] == resource_user_id
        return True

    # For :any permissions, check organization scope
    if permission.endswith(":any") or ":read:" in permission:
        if resource_org_id is not None:
            user_org = user.get("organization_id")
            return user_org == resource_org_id
        return True

    return True


def filter_accessible_resources(
    user: dict[str, Any],
    resources: list[Any],
    permission: str,
    user_id_attr: str = "user_id",
) -> list[Any]:
    """Filter a list of resources to only those the user can access."""
    role = user.get("role", "driver")

    if role == "admin":
        return resources

    if permission.endswith(":all"):
        return resources

    if permission.endswith(":own") or permission.endswith(":read"):
        return [r for r in resources if getattr(r, user_id_attr, None) == user["id"]]

    if permission.endswith(":any"):
        user_org = user.get("organization_id")
        return [
            r
            for r in resources
            if getattr(r, user_id_attr, None) == user["id"]
            or (user_org and getattr(r, "organization_id", None) == user_org)
        ]

    return resources


def role_from_db(db_user) -> str:
    """Extract role string from a database User row, defaulting to 'driver'."""
    return getattr(db_user, "role", "driver") or "driver"


# ── API Key Scope Checking ──────────────────────────────────────


def require_scope(scope: str) -> Callable:
    """
    FastAPI dependency factory that checks an API key has the required scope.

    API keys are identified by the ``vhm_`` prefix in the Authorization header.
    For regular user tokens (session / OAuth2), this dependency falls through
    to the regular permission check.

    Usage::

        @router.get("/vehicles",
                    dependencies=[Depends(require_scope("vehicles:read"))])
        async def list_vehicles():
            ...

    Scopes are defined when the API key is created (see ``db.create_api_key``).
    The scope ``*`` grants all scopes.
    """

    async def scope_checker(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> dict[str, Any]:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header (Bearer <token or API key>)",
            )

        token = credentials.credentials

        # ── API key flow (starts with "vhm_") ──
        if token.startswith("vhm_"):
            return await _check_api_key_scope(token, scope)

        # ── Regular token flow (session / OAuth2) ──
        from api.dependencies import get_current_user

        user = await get_current_user()

        # Map scope to a permission check for the user's role
        from auth.abac import check_permission as abac_check

        if not abac_check(user, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' denied for user",
            )
        return user

    return scope_checker


async def _check_api_key_scope(token: str, required_scope: str) -> dict[str, Any]:
    """Validate an API key and check it has the required scope."""
    from core.db import APIKey, User, get_session, hash_api_key

    parts = token.split(".", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format (expected 'prefix.secret')",
        )

    prefix, key_secret = parts
    key_hash = hash_api_key(prefix, key_secret)

    db_session = get_session()
    try:
        api_key = (
            db_session.query(APIKey)
            .filter_by(
                key_hash=key_hash,
                is_active=True,
            )
            .first()
        )

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
            )

        # Check expiry
        if api_key.expires_at:
            expires = api_key.expires_at
            if expires.tzinfo is not None:
                expires = expires.replace(tzinfo=None)
            if expires < datetime.now(UTC).replace(tzinfo=None):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                )

        # Check scope
        scopes: list[str] = json.loads(api_key.scopes or "[]")
        if required_scope not in scopes and "*" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: '{required_scope}'",
            )

        # Get user info
        user = db_session.query(User).filter_by(id=api_key.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Update last_used_at
        api_key.last_used_at = datetime.now(UTC)
        db_session.commit()

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role or "driver",
            "organization_id": user.organization_id,
            "name": user.name,
            "email": user.email,
            "auth_method": "api_key",
            "api_key_id": api_key.id,
            "scope": required_scope,
        }
    finally:
        db_session.close()
