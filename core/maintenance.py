"""
Maintenance Scheduling and Upcoming Service Forecast module.
Predicts routine service schedules based on vehicle mileage and service history.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from typing import Any


SERVICE_RULES = [
    {"type": "Engine Oil & Filter Change", "interval_km": 8000, "interval_days": 90},
    {"type": "Tire Rotation & Alignment", "interval_km": 12000, "interval_days": 180},
    {"type": "Brake System Inspection", "interval_km": 15000, "interval_days": 270},
    {"type": "Coolant & Fluid Flush", "interval_km": 30000, "interval_days": 365},
    {"type": "Air & Cabin Filter Replacement", "interval_km": 15000, "interval_days": 180},
]


def predict_upcoming_maintenance(
    vehicle: Any,
    last_records: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Predicts upcoming maintenance items for a vehicle.
    Returns list of items with service_type, due_date, status ('overdue', 'due_soon', 'ok').
    """
    results = []
    current_date = date.today()
    mileage = float(getattr(vehicle, "mileage", 0.0) or 0.0)
    last_service = getattr(vehicle, "last_service_date", None)

    for rule in SERVICE_RULES:
        service_type = rule["type"]
        
        # Check if there is a recorded service for this type
        matched_date = last_service
        if last_records:
            for rec in last_records:
                r_type = str(getattr(rec, "service_type", ""))
                r_date = getattr(rec, "service_date", None)
                if service_type.lower() in r_type.lower() and r_date:
                    matched_date = r_date
                    break

        if not matched_date:
            matched_date = current_date - timedelta(days=rule["interval_days"] - 10)

        if isinstance(matched_date, datetime):
            matched_date = matched_date.date()

        days_since = (current_date - matched_date).days
        days_remaining = rule["interval_days"] - days_since

        due_date = current_date + timedelta(days=max(1, days_remaining))

        if days_remaining <= 0:
            status = "overdue"
            urgency_msg = f"Overdue by {abs(days_remaining)} days"
        elif days_remaining <= 15:
            status = "due_soon"
            urgency_msg = f"Due in {days_remaining} days"
        else:
            status = "ok"
            urgency_msg = f"Due in ~{days_remaining} days"

        results.append({
            "service_type": service_type,
            "due_date": due_date.isoformat(),
            "status": status,
            "urgency_msg": urgency_msg,
            "interval_km": rule["interval_km"],
        })

    return sorted(results, key=lambda x: 0 if x["status"] == "overdue" else (1 if x["status"] == "due_soon" else 2))
