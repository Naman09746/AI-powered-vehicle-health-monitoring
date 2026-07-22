"""
Fleet router — fleet-wide overview with aggregated health stats.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from api.db_proxy import (
    async_get_active_alerts,
    async_get_latest_prediction,
    async_get_sensor_readings,
    async_get_vehicles_for_user,
)
from api.dependencies import get_current_user
from core.health_score import calculate_health_score
from core.logger import get_logger

log = get_logger("api.fleet")
router = APIRouter(prefix="/api/v1/fleet", tags=["fleet"])


@router.get("/overview")
async def fleet_overview(
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get aggregated fleet overview."""
    vehicles = await async_get_vehicles_for_user(user["id"])
    total_vehicles = len(vehicles)

    if total_vehicles == 0:
        return {
            "vehicle_count": 0,
            "avg_health_score": None,
            "healthy_count": 0,
            "at_risk_count": 0,
            "critical_count": 0,
            "total_active_alerts": 0,
        }

    async def fetch_vehicle_data(v):
        readings_task = async_get_sensor_readings(v.id, user["id"], limit=1)
        pred_task = async_get_latest_prediction(v.id, user["id"])
        alerts_task = async_get_active_alerts(user["id"], v.id)
        readings, pred, alerts = await asyncio.gather(
            readings_task, pred_task, alerts_task
        )
        return readings, pred, alerts

    results = await asyncio.gather(*(fetch_vehicle_data(v) for v in vehicles))

    healthy_count = 0
    at_risk_count = 0
    critical_count = 0
    total_health = 0.0
    total_active_alerts = 0

    for readings, pred, alerts in results:
        if not readings.empty:
            health_result = calculate_health_score(
                sensor_data=readings.iloc[-1],
                failure_prob=pred.failure_prob if pred else None,
            )
            score = health_result.get("score", 50)
            total_health += score
            if score >= 95:
                healthy_count += 1
            elif score >= 60:
                at_risk_count += 1
            else:
                critical_count += 1

        total_active_alerts += len(alerts)

    avg_health = round(total_health / total_vehicles, 1) if total_vehicles > 0 else None

    return {
        "vehicle_count": total_vehicles,
        "avg_health_score": avg_health,
        "healthy_count": healthy_count,
        "at_risk_count": at_risk_count,
        "critical_count": critical_count,
        "total_active_alerts": total_active_alerts,
    }
