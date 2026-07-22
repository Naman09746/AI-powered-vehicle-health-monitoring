"""
History router — maintenance records CRUD.
"""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import core.db as database
from api.dependencies import get_current_user
from core.logger import get_logger

log = get_logger("api.history")
router = APIRouter(prefix="/api/v1/history", tags=["history"])


class MaintenanceCreate(BaseModel):
    service_date: str | None = None
    service_type: str
    parts_replaced: str | None = None
    cost: float | None = None
    notes: str | None = None


class MaintenanceUpdate(BaseModel):
    service_date: str | None = None
    service_type: str | None = None
    parts_replaced: str | None = None
    cost: float | None = None
    notes: str | None = None


@router.get("/{vehicle_id}")
async def list_history(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """List maintenance history for a vehicle."""
    return database.get_maintenance_history(vehicle_id, user["id"])


@router.post("/{vehicle_id}")
async def create_history(
    vehicle_id: int,
    body: MaintenanceCreate,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Add a maintenance record."""
    record = database.create_maintenance_record(
        user_id=user["id"],
        vehicle_id=vehicle_id,
        service_date=body.service_date or datetime.date.today().isoformat(),
        service_type=body.service_type,
        parts_replaced=body.parts_replaced,
        cost=body.cost,
        notes=body.notes,
    )
    return record


@router.put("/{vehicle_id}/{record_id}")
async def update_history(
    vehicle_id: int,
    record_id: int,
    body: MaintenanceUpdate,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Update a maintenance record."""
    kwargs = {k: v for k, v in body.dict().items() if v is not None}
    success = database.update_maintenance_record(record_id, user["id"], **kwargs)
    if not success:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "updated"}


@router.delete("/{vehicle_id}/{record_id}")
async def delete_history(
    vehicle_id: int,
    record_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Delete a maintenance record."""
    success = database.delete_maintenance_record(record_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"status": "deleted"}
