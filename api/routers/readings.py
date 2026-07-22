"""
Sensor readings ingestion and retrieval router.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

import core.db as database
from api.dependencies import get_current_user
from api.schemas.vehicle import SensorReadingIn, SensorReadingResponse
from core.logger import get_logger

log = get_logger("api_readings")

router = APIRouter(prefix="/api/v1/vehicles/{vehicle_id}/readings", tags=["readings"])


@router.post("", status_code=201)
async def ingest_reading(
    vehicle_id: int,
    body: SensorReadingIn,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Ingest a single sensor reading for a vehicle."""
    # Verify vehicle access
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    from core.preprocessing import preprocess_single_reading

    cleaned, errors = preprocess_single_reading(body.model_dump())
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    upload_id = database.get_or_create_default_upload(vehicle_id, user["id"])

    reading = database.SensorReading(
        upload_id=upload_id,
        vehicle_id=vehicle_id,
        user_id=user["id"],
        timestamp=datetime.fromisoformat(cleaned["timestamp"]),
        failure_label=0,
        **{
            col: cleaned.get(col)
            for col in [
                "engine_temp",
                "oil_pressure",
                "coolant_temp",
                "engine_rpm",
                "vibration",
                "fuel_consumption",
                "battery_voltage",
                "tire_pressure",
                "speed",
                "engine_load",
            ]
        },
    )
    session = database.get_session()
    try:
        session.add(reading)
        session.commit()
        session.refresh(reading)
    except Exception:
        session.rollback()
        log.exception("Failed to store reading")
        raise HTTPException(status_code=500, detail="Failed to store reading")
    finally:
        session.close()

    # Run alert engine
    from core.alerts import check_and_generate_alerts

    alerts = check_and_generate_alerts(cleaned, vehicle_id, user["id"])

    return {
        "status": "ok",
        "reading_id": reading.id,
        "alerts_generated": len(alerts),
    }


@router.get("", response_model=list[SensorReadingResponse])
async def list_readings(
    vehicle_id: int,
    limit: int = Query(100, ge=1, le=1000),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get recent sensor readings for a vehicle."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    df = database.get_sensor_readings(vehicle_id, user["id"])
    if df.empty:
        return []

    df = df.tail(limit)
    return df.to_dict(orient="records")
