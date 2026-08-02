"""
Vehicle CRUD router with Health Score enrichment.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

import core.db as database
from api.dependencies import get_current_user
from api.schemas.vehicle import VehicleCreate, VehicleResponse
from core.health_score import compute_health_score, get_health_status

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


def _enrich_vehicle(vehicle: Any, user_id: int) -> dict[str, Any]:
    """Attaches health_score and health_status to a vehicle model instance."""
    import os
    if os.getenv("AUTO_SIMULATE", "false").lower() == "true":
        try:
            from api.routers.simulator import ensure_vehicle_simulation
            ensure_vehicle_simulation(vehicle.id, user_id, vehicle.vehicle_id_display)
        except Exception:
            pass

    latest = database.get_latest_reading_dict(vehicle.id, user_id)
    score = compute_health_score(latest)
    status_str = get_health_status(score)

    v_dict = {
        "id": vehicle.id,
        "user_id": vehicle.user_id,
        "vehicle_id_display": vehicle.vehicle_id_display,
        "model": vehicle.model,
        "manufacturing_year": vehicle.manufacturing_year,
        "engine_type": vehicle.engine_type,
        "mileage": vehicle.mileage,
        "last_service_date": vehicle.last_service_date,
        "created_at": vehicle.created_at,
        "health_score": score,
        "health_status": status_str,
    }
    return v_dict


@router.get("", response_model=list[VehicleResponse])
async def list_vehicles(
    user: dict[str, Any] = Depends(get_current_user),
):
    """List all vehicles for the authenticated user."""
    vehicles = database.get_vehicles_for_user(user["id"])
    return [_enrich_vehicle(v, user["id"]) for v in vehicles]


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
    from core.audit import log_audit_event
    log_audit_event(user["id"], "vehicle.created", resource_type="Vehicle", resource_id=vehicle.id, details={"display_id": vehicle.vehicle_id_display})

    # Start high-speed telemetry simulation (2-second interval) & seed initial 20 readings instantly
    try:
        from api.routers.simulator import ensure_vehicle_simulation
        ensure_vehicle_simulation(vehicle.id, user["id"], vehicle.vehicle_id_display, interval=2.0)
    except Exception:
        pass

    return _enrich_vehicle(vehicle, user["id"])


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get a specific vehicle."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _enrich_vehicle(vehicle, user["id"])


@router.delete("/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Delete a vehicle and its telemetry history."""
    success = database.delete_vehicle(vehicle_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    from core.audit import log_audit_event
    log_audit_event(user["id"], "vehicle.deleted", resource_type="Vehicle", resource_id=vehicle_id)

    return {"status": "success", "message": f"Vehicle {vehicle_id} deleted."}

