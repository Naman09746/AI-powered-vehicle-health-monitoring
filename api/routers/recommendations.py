"""
Recommendations router — combines alerts, predictions, and sensor deviations into actionable recommendations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

import core.db as database
from api.dependencies import get_current_user
from core.logger import get_logger

log = get_logger("api.recommendations")
router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.get("/{vehicle_id}")
async def list_recommendations(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Get alerts and recommendations for a vehicle."""
    alerts = database.get_active_alerts(user["id"], vehicle_id)

    # Get latest sensor reading for deviation analysis
    from ml.ml_models import get_sensor_deviations

    readings = database.get_sensor_readings(vehicle_id, user["id"], limit=1)
    deviations = []
    if not readings.empty:
        deviations = get_sensor_deviations(readings.iloc[0])

    # Build recommendation items from core.alerts + deviations
    recommendations = []

    for alert in alerts[:10]:
        recommendations.append(
            {
                "type": "alert",
                "id": alert.id,
                "message": alert.message,
                "severity": alert.severity,
                "alert_type": alert.alert_type,
                "created_at": str(alert.created_at) if alert.created_at else None,
                "is_dismissed": alert.is_dismissed,
            }
        )

    for d in deviations[:5]:
        if d["deviation_pct"] > 0:
            recommendations.append(
                {
                    "type": "deviation",
                    "sensor": d["sensor"],
                    "label": d["label"],
                    "value": d["value"],
                    "unit": d["unit"],
                    "deviation_pct": d["deviation_pct"],
                    "status": d["status"],
                    "normal_range": d["normal_range"],
                }
            )

    return {
        "alerts": alerts,
        "deviations": deviations,
        "recommendations": recommendations,
    }
