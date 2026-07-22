"""
Dashboard router — aggregated data for the dashboard view.
Includes SSE streaming for real-time updates.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

import core.db as database
from api.db_proxy import (
    async_get_active_alerts,
    async_get_latest_prediction,
    async_get_sensor_readings,
    async_get_vehicle_by_id,
)
from api.dependencies import get_current_user
from api.pagination import CursorPage, PaginationParams, paginate_query
from core.health_score import calculate_health_score
from core.logger import get_logger

log = get_logger("api.dashboard")
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/{vehicle_id}")
async def get_dashboard(
    vehicle_id: int,
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get aggregated dashboard data for a vehicle."""
    payload = await _build_dashboard_payload(vehicle_id, user["id"])
    if "error" in payload:
        raise HTTPException(status_code=404, detail=payload["error"])

    # Cache for 30 seconds (SSE handles real-time)
    response.headers["Cache-Control"] = "max-age=30, private"
    return payload


@router.get("/{vehicle_id}/readings", response_model=CursorPage[dict])
async def get_dashboard_readings(
    vehicle_id: int,
    params: PaginationParams = Depends(),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get paginated sensor readings for a vehicle."""
    from sqlalchemy import select

    from api.database import get_async_session

    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    async with get_async_session():
        from core.db import SensorReading

        query = select(SensorReading).filter_by(
            vehicle_id=vehicle_id, user_id=user["id"]
        )
        items, next_cursor, has_more = await paginate_query(
            query, params, cursor_field="timestamp", descending=True
        )
        return CursorPage(
            items=[r.__dict__ for r in items],
            next_cursor=next_cursor,
            has_more=has_more,
        )


# ── SSE streaming endpoint ─────────────────────────────────────


async def _build_dashboard_payload(vehicle_id: int, user_id: int) -> dict[str, Any]:
    """Build the full dashboard payload (shared between REST and SSE)."""
    vehicle = await async_get_vehicle_by_id(vehicle_id, user_id)
    if not vehicle:
        return {"error": "Vehicle not found"}

    readings = await async_get_sensor_readings(vehicle_id, user_id, limit=50)
    recent_readings = readings
    active_alerts = await async_get_active_alerts(user_id, vehicle_id)
    latest_pred = await async_get_latest_prediction(vehicle_id, user_id)

    health_result = calculate_health_score(
        sensor_data=readings.iloc[-1] if not readings.empty else {},
        failure_prob=latest_pred.failure_prob if latest_pred else None,
    )
    health_score = health_result.get("score", 50)
    health_band = health_result.get("band_name", "Unknown")

    return {
        "vehicle": {
            "id": vehicle.id,
            "vehicle_id_display": vehicle.vehicle_id_display,
            "model": vehicle.model,
            "manufacturing_year": vehicle.manufacturing_year,
            "engine_type": vehicle.engine_type,
            "mileage": vehicle.mileage,
            "last_service_date": str(vehicle.last_service_date)
            if vehicle.last_service_date
            else None,
        },
        "recent_readings": recent_readings.to_dict(orient="records")
        if hasattr(recent_readings, "to_dict")
        else [],
        "health_score": health_score,
        "health_band": health_band,
        "active_alerts": len(active_alerts),
        "total_readings": len(readings),
        "latest_prediction": {
            "prediction": latest_pred.prediction if latest_pred else None,
            "failure_prob": latest_pred.failure_prob if latest_pred else None,
        }
        if latest_pred
        else None,
    }


@router.get("/{vehicle_id}/stream")
async def dashboard_sse_stream(
    vehicle_id: int,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
):
    """
    SSE endpoint for real-time dashboard updates.

    Client connects via EventSource:
      new EventSource("/api/v1/dashboard/{vehicle_id}/stream")

    Sends a full dashboard payload every 5 seconds, plus a heartbeat
    every 30s to keep the connection alive.
    """
    # Verify vehicle ownership upfront
    vehicle = await async_get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    async def event_generator():
        last_payload = ""
        heartbeat_interval = 0

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                payload = await _build_dashboard_payload(vehicle_id, user["id"])

                payload_json = json.dumps(payload)

                # Only send if data changed (avoid flooding)
                if payload_json != last_payload:
                    yield f"data: {payload_json}\n\n"
                    last_payload = payload_json
                    heartbeat_interval = 0
                else:
                    # Send heartbeat every ~30s (6 iterations × 5s)
                    heartbeat_interval += 1
                    if heartbeat_interval >= 6:
                        yield f": heartbeat {time.time()}\n\n"
                        heartbeat_interval = 0

                await asyncio.sleep(5)

            except Exception as exc:
                log.warning("SSE error for vehicle %d: %s", vehicle_id, exc)
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
