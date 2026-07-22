"""
Alerts router — list, acknowledge, dismiss.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import core.db as database
from api.dependencies import get_current_user
from api.schemas.vehicle import AlertAcknowledge, AlertResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    vehicle_id: int | None = None,
    active_only: bool = True,
    user: dict[str, Any] = Depends(get_current_user),
):
    """List alerts, optionally filtering by vehicle and status."""
    if active_only:
        alerts = database.get_active_alerts(user["id"], vehicle_id)
    else:
        alerts = database.get_all_alerts(user["id"], vehicle_id)
    return alerts


@router.patch("/{alert_id}/dismiss", response_model=dict)
async def dismiss_alert(
    alert_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Dismiss an alert."""
    dismissed = database.dismiss_alert(alert_id, user["id"])
    if not dismissed:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "ok", "detail": "Alert dismissed"}


@router.patch("/{alert_id}/acknowledge", response_model=dict)
async def acknowledge_alert(
    alert_id: int,
    body: AlertAcknowledge,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Acknowledge an alert (mark as seen by a specific user)."""
    acked = database.acknowledge_alert(alert_id, user["id"], body.acknowledged_by)
    if not acked:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "ok", "detail": "Alert acknowledged"}
