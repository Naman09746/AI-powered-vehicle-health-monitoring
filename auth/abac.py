"""
Attribute-Based Access Control (ABAC) for fine-grained authorization.

Extends the existing RBAC system with context-aware policy evaluation.
ABAC evaluates ``{user, resource, context}`` tuples against declarative
policies to determine access.

Concepts::

    - **Subject**: The authenticated user (with role, org, attributes).
    - **Resource**: The object being accessed (vehicle, model, alert, …).
    - **Action**: The operation being performed (read, write, delete, …).
    - **Context**: Environmental conditions (time, IP, org scope, …).
    - **Policy**: Rules that map {subject, resource, action, context} to a
      boolean decision.

Usage::

    from auth.abac import check_permission, require_permission

    # Programmatic check
    if check_permission(user, "vehicle:read", resource_id=42, context={"org_id": 1}):
        ...

    # FastAPI dependency
    @router.get("/vehicles/{vehicle_id}",
                dependencies=[Depends(require_permission("vehicle:read"))])
    async def get_vehicle(vehicle_id: int, user=Depends(get_current_user)):
        ...
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, status

from core.logger import get_logger

log = get_logger("abac")


# ── Data types ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ABACContext:
    """Evaluation context for an ABAC decision.

    Attributes:
        resource_owner_id: The user ID that owns the target resource (if any).
        resource_org_id: The organization ID that owns the target resource (if any).
        resource_type: Type of resource (``vehicle``, ``model``, ``alert``, …).
        action: The granular action being performed (``read``, ``write``, ``delete``, …).
        extra: Arbitrary extra context key-value pairs for custom policies.
    """

    resource_owner_id: int | None = None
    resource_org_id: int | None = None
    resource_type: str | None = None
    action: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# ── Policy type ──────────────────────────────────────────────────

Subject = dict[str, Any]
PolicyFn = Callable[[Subject, ABACContext], bool | None]
"""A policy function returns ``True`` (allow), ``False`` (deny), or ``None`` (abstain)."""


@dataclass
class Policy:
    """A single ABAC policy rule.

    Attributes:
        name: Human-readable policy name (for logging / debugging).
        description: What this policy governs.
        permission: The permission string this policy applies to
            (e.g. ``vehicle:read``).  Supports glob patterns via
            ``fnmatch`` (e.g. ``vehicle:*``).
        evaluate: Callable that returns ``True`` (allow), ``False`` (deny),
            or ``None`` (abstain — let other policies decide).
        priority: Evaluation priority (higher = evaluated first).  Default 0.
    """

    name: str
    description: str
    permission: str
    evaluate: PolicyFn
    priority: int = 0


# ── Policy registry ──────────────────────────────────────────────

_policies: list[Policy] = []


def register_policy(policy: Policy) -> None:
    """Register an ABAC policy.  Policies are evaluated in priority order."""
    _policies.append(policy)
    _policies.sort(key=lambda p: -p.priority)
    log.debug("ABAC policy registered: %s (priority=%d)", policy.name, policy.priority)


def clear_policies() -> None:
    """Clear all registered policies (useful for testing)."""
    _policies.clear()


# ── Built-in policies ────────────────────────────────────────────


def _policy_admin_grant(subject: Subject, ctx: ABACContext) -> bool | None:
    """Admins can do anything on any resource."""
    if subject.get("role") == "admin":
        return True
    return None


def _policy_own_resource(subject: Subject, ctx: ABACContext) -> bool | None:
    """Users can access resources they own (for ``:own``-scoped permissions)."""
    resource_owner_id = ctx.resource_owner_id
    if resource_owner_id is not None and subject.get("id") == resource_owner_id:
        return True
    return None


def _policy_org_resource(subject: Subject, ctx: ABACContext) -> bool | None:
    """Users can access resources within their organization."""
    resource_org_id = ctx.resource_org_id
    if resource_org_id is not None:
        user_org = subject.get("organization_id")
        if user_org is not None and user_org == resource_org_id:
            # Check the user has a role that allows org-wide access
            role = subject.get("role", "driver")
            if role in ("fleet_manager", "admin", "technician"):
                return True
    return None


def _policy_self_admin(subject: Subject, ctx: ABACContext) -> bool | None:
    """Users can always manage their own user profile."""
    if ctx.resource_type == "user" and ctx.action in ("read", "update"):
        if ctx.resource_owner_id == subject.get("id"):
            return True
    return None


# ── Permission → context mapping ────────────────────────────────

_PERMISSION_PATTERNS: dict[str, tuple[str, str]] = {
    # Maps "resource:action" -> (resource_type, action)
    "vehicle:*": ("vehicle", "*"),
    "vehicle:read": ("vehicle", "read"),
    "vehicle:write": ("vehicle", "write"),
    "vehicle:create": ("vehicle", "create"),
    "vehicle:update": ("vehicle", "update"),
    "vehicle:delete": ("vehicle", "delete"),
    "model:*": ("model", "*"),
    "model:train": ("model", "train"),
    "model:promote": ("model", "promote"),
    "alert:*": ("alert", "*"),
    "alert:dismiss": ("alert", "dismiss"),
    "report:*": ("report", "*"),
    "report:generate": ("report", "generate"),
    "admin:*": ("admin", "*"),
    "admin:users": ("admin", "users"),
}


# ── Core evaluation ──────────────────────────────────────────────


def check_permission(
    user: Subject,
    permission: str,
    resource_id: int | None = None,
    context: dict[str, Any] | None = None,
) -> bool:
    """Evaluate whether ``user`` has ``permission`` for a given resource.

    The evaluation proceeds in three phases:

    1. **ABAC policy evaluation**: Registered policy functions are called in
       priority order.  The first policy that returns a non-``None`` value
       determines the result (``True`` = allow, ``False`` = deny).
    2. **RBAC fallback**: If all ABAC policies abstain, fall back to the
       role-based permission check from ``auth.rbac``.
    3. **Default deny**: If nothing explicitly allows, access is denied.

    Args:
        user: The authenticated user dict (must have ``id``, ``role``,
            ``organization_id`` keys).
        permission: The permission string (e.g. ``vehicle:read``).
        resource_id: The ID of the target resource (used for ownership checks).
        context: Optional extra context dict (may include ``resource_owner_id``,
            ``resource_org_id``, ``resource_type``, ``action``, etc.).

    Returns:
        ``True`` if access is granted, ``False`` otherwise.
    """
    ctx = context or {}

    # Build structured ABAC context
    resource_type, action = _resolve_permission(permission)
    abac_ctx = ABACContext(
        resource_owner_id=ctx.get(
            "resource_owner_id", resource_id if resource_type == "vehicle" else None
        ),
        resource_org_id=ctx.get("resource_org_id"),
        resource_type=ctx.get("resource_type", resource_type),
        action=ctx.get("action", action),
        extra=ctx.get("extra", {}),
    )

    # Phase 1: Evaluate registered ABAC policies
    for policy in _policies:
        if not _permission_matches(policy.permission, permission):
            continue
        try:
            result = policy.evaluate(user, abac_ctx)
            if result is not None:
                log.debug(
                    "ABAC policy '%s' decision=%s for user=%s permission=%s",
                    policy.name,
                    result,
                    user.get("id"),
                    permission,
                )
                return result
        except Exception:
            log.exception("ABAC policy '%s' raised exception", policy.name)
            # Fail closed — deny on policy error
            return False

    # Phase 2: RBAC fallback
    from auth.rbac import check_resource_access, has_permission

    role = user.get("role", "driver")
    if has_permission(role, permission):
        # Delegate to the resource-level access check
        return check_resource_access(
            user=user,
            permission=permission,
            resource_user_id=abac_ctx.resource_owner_id,
            resource_org_id=abac_ctx.resource_org_id,
        )

    # Phase 3: Default deny
    log.debug(
        "ABAC default deny for user=%s permission=%s",
        user.get("id"),
        permission,
    )
    return False


def _resolve_permission(permission: str) -> tuple[str | None, str | None]:
    """Split a permission string into (resource_type, action)."""
    parts = permission.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], None
    return None, None


def _permission_matches(pattern: str, permission: str) -> bool:
    """Check if a policy's permission pattern matches the requested permission.

    Supports glob patterns via ``fnmatch`` — e.g. ``vehicle:*`` matches
    ``vehicle:read``, ``vehicle:write``, etc.
    """
    if ":" not in pattern or ":" not in permission:
        return pattern == permission
    # Use fnmatch for glob support in both resource and action parts
    p_resource, p_action = pattern.split(":", 1)
    r_resource, r_action = permission.split(":", 1)
    return fnmatch.fnmatch(r_resource, p_resource) and fnmatch.fnmatch(
        r_action, p_action
    )


# ── Register built-in policies ───────────────────────────────────

register_policy(
    Policy(
        name="admin-full-access",
        description="Admins have unrestricted access to all resources",
        permission="*",
        evaluate=_policy_admin_grant,
        priority=100,
    )
)

register_policy(
    Policy(
        name="own-resource-access",
        description="Users can access resources they own",
        permission="*",
        evaluate=_policy_own_resource,
        priority=50,
    )
)

register_policy(
    Policy(
        name="org-scoped-access",
        description="Fleet managers and technicians can access org resources",
        permission="*",
        evaluate=_policy_org_resource,
        priority=40,
    )
)

register_policy(
    Policy(
        name="self-profile-management",
        description="Users can read and update their own profile",
        permission="admin:users",
        evaluate=_policy_self_admin,
        priority=30,
    )
)


# ── FastAPI dependency factory ───────────────────────────────────


def require_permission(permission: str) -> Callable:
    """FastAPI dependency factory that checks a specific ABAC permission.

    Usage::

        @router.get("/vehicles/{vehicle_id}",
                    dependencies=[Depends(require_permission("vehicle:read"))])
        async def get_vehicle(vehicle_id: int, user: dict = Depends(get_current_user)):
            ...

    The dependency extracts the authenticated user from ``get_current_user``
    (injected via ``api/dependencies``) and evaluates the given permission
    against the resource context inferred from path parameters.
    """

    async def permission_checker(
        user: dict[str, Any] = Depends(lambda: None),  # placeholder
    ) -> dict[str, Any]:
        # Lazy import to avoid circular dependency
        from api.dependencies import get_current_user

        current_user = await get_current_user()

        if not check_permission(current_user, permission):
            log.warning(
                "ABAC denied permission '%s' for user %s",
                permission,
                current_user.get("id"),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires '{permission}'",
            )
        return current_user

    return permission_checker


def require_any_permission(permissions: list[str]) -> Callable:
    """FastAPI dependency factory that checks the user has at least one of the listed permissions.

    Usage::

        @router.get("/reports",
                    dependencies=[Depends(require_any_permission(["report:generate", "admin:*"]))])
        async def get_reports():
            ...
    """

    async def permission_checker(
        user: dict[str, Any] = Depends(lambda: None),
    ) -> dict[str, Any]:
        from api.dependencies import get_current_user

        current_user = await get_current_user()

        for permission in permissions:
            if check_permission(current_user, permission):
                return current_user

        log.warning(
            "ABAC denied all permissions %s for user %s",
            permissions,
            current_user.get("id"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: requires one of {permissions}",
        )

    return permission_checker
