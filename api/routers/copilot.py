"""Maintenance copilot + root cause analysis API (AF-09, AF-10)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

import core.db as database
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/copilot", tags=["copilot"])


@router.post("/analyze/{vehicle_id}")
async def analyze_vehicle(
    vehicle_id: int, user: dict[str, Any] = Depends(get_current_user)
):
    """Get a natural-language health analysis for a vehicle."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")

    readings = database.get_sensor_readings(vehicle_id, user["id"])
    recent = readings.tail(100) if len(readings) > 100 else readings
    alerts = database.get_active_alerts(user["id"], vehicle_id)
    pred = database.get_latest_prediction(vehicle_id, user["id"])

    from ml.copilot import analyze_vehicle_health

    result = analyze_vehicle_health(
        vehicle_info={"vehicle_id_display": vehicle.vehicle_id_display},
        recent_readings=recent.to_dict(orient="records")
        if hasattr(recent, "to_dict")
        else [],
        predictions=[{"failure_prob": pred.failure_prob}] if pred else None,
        alerts=[
            {"id": a.id, "severity": a.severity, "message": a.message} for a in alerts
        ],
    )
    result["vehicle"] = {
        "id": vehicle.id,
        "vehicle_id_display": vehicle.vehicle_id_display,
    }
    return result


@router.post("/report/{vehicle_id}")
async def generate_report(
    vehicle_id: int, user: dict[str, Any] = Depends(get_current_user)
):
    """Generate a plain-text maintenance report."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")
    readings = database.get_sensor_readings(vehicle_id, user["id"])
    pred = database.get_latest_prediction(vehicle_id, user["id"])

    from ml.copilot import generate_report

    return {
        "report": generate_report(
            {"vehicle_id_display": vehicle.vehicle_id_display},
            readings.to_dict(orient="records") if hasattr(readings, "to_dict") else [],
            [{"failure_prob": pred.failure_prob}] if pred else None,
        )
    }


@router.post("/root-cause/{vehicle_id}")
async def root_cause_analysis(
    vehicle_id: int, user: dict[str, Any] = Depends(get_current_user)
):
    """Analyze sensor correlations to find root causes."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")

    df = database.get_sensor_readings(vehicle_id, user["id"])
    if df.empty:
        raise HTTPException(400, "No sensor data available")

    from ml.anomaly import EnsembleAnomalyDetector
    from ml.root_cause import analyze_sensor_correlations

    # Detect anomalies first
    detector = EnsembleAnomalyDetector()
    anomaly_result = detector.analyze(df)

    # Find correlations
    correlation_result = analyze_sensor_correlations(df)

    # Trace failure chain
    from ml.root_cause import trace_failure_chain

    anomalous_sensors = [s["sensor"] for s in anomaly_result.get("flagged_sensors", [])]
    chain = trace_failure_chain(
        anomalous_sensors, correlation_result.get("pairwise_correlations", [])
    )

    return {
        "vehicle_id": vehicle_id,
        "anomalies": anomaly_result,
        "correlations": correlation_result,
        "failure_chain": chain,
        "total_readings_analyzed": len(df),
    }
