"""
Vehicle CRUD router.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

import core.db as database
from api.dependencies import get_current_user
from api.schemas.vehicle import VehicleCreate, VehicleResponse

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleResponse])
async def list_vehicles(
    user: dict[str, Any] = Depends(get_current_user),
):
    """List all vehicles for the authenticated user."""
    return database.get_vehicles_for_user(user["id"])


@router.post("", response_model=VehicleResponse, status_code=201)
async def create_vehicle(
    body: VehicleCreate,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Register a new vehicle."""
    vehicle = database.create_vehicle(
        user_id=user["id"],
        vehicle_id_display=body.vehicle_id_display,
        model=body.model,
        manufacturing_year=body.manufacturing_year,
        engine_type=body.engine_type,
        mileage=body.mileage,
        last_service_date=body.last_service_date,
    )
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle '{body.vehicle_id_display}' already exists",
        )
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get a specific vehicle."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle
