"""Multi-tenancy: organization & team management (AF-05)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import core.db as database
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/org", tags=["organizations"])


@router.get("")
async def get_org(user: dict[str, Any] = Depends(get_current_user)):
    """Get current user's organization details."""
    org_id = user.get("organization_id")
    if not org_id:
        raise HTTPException(404, "No organization assigned")
    org = database.get_organization(org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    members = database.get_all_users(org_id)
    return {
        "id": org.id,
        "name": org.name,
        "plan": org.plan,
        "member_count": len(members),
    }


@router.get("/members")
async def list_members(user: dict[str, Any] = Depends(get_current_user)):
    """List members in the user's organization."""
    if user.get("role") not in ("admin", "fleet_manager"):
        raise HTTPException(403, "Insufficient permissions")
    members = database.get_all_users(user.get("organization_id"))
    return [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "role": u.role,
            "email": u.email,
        }
        for u in members
    ]


@router.patch("/members/{member_id}/role")
async def update_member_role(
    member_id: int, role: str, user: dict[str, Any] = Depends(get_current_user)
):
    """Update a member's role (admin only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    valid_roles = {"admin", "fleet_manager", "technician", "driver"}
    if role not in valid_roles:
        raise HTTPException(400, f"Invalid role. Valid: {valid_roles}")
    return {"success": database.update_user_role(member_id, role)}


@router.get("/vehicles")
async def org_vehicles(user: dict[str, Any] = Depends(get_current_user)):
    """List all vehicles in the organization."""

    import core.db as database

    org_id = user.get("organization_id")
    if not org_id:
        raise HTTPException(404, "No organization")
    session = database.get_session()
    try:
        vehicles = (
            session.query(database.Vehicle)
            .join(database.User)
            .filter(database.User.organization_id == org_id)
            .all()
        )
        return [
            {
                "id": v.id,
                "vehicle_id_display": v.vehicle_id_display,
                "model": v.model,
                "owner": v.user_id,
            }
            for v in vehicles
        ]
    finally:
        session.close()
