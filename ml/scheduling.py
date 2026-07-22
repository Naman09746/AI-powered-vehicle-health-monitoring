"""
Predictive maintenance scheduling based on usage heuristics and sensor trends.
Recommends optimal service windows and part replacement timelines.
"""

import datetime
from typing import Any

from core.config import PRIORITY_SERVICE_WINDOWS

# ── Part lifespan defaults (miles / days / hours) ─────────────────────────
_PART_LIFESPAN_ESTIMATES: dict[str, dict[str, float]] = {
    "brakes": {"mileage_max": 50000, "days_max": 730, "label": "Brake Pads"},
    "tires": {"mileage_max": 60000, "days_max": 1095, "label": "Tires"},
    "battery": {"mileage_max": 40000, "days_max": 1095, "label": "Battery"},
    "oil": {"mileage_max": 7500, "days_max": 180, "label": "Oil Change"},
    "coolant": {"mileage_max": 30000, "days_max": 730, "label": "Coolant Flush"},
}

# ── Mileage thresholds per driving condition ──────────────────────────────
_CONDITION_MULTIPLIERS: dict[str, float] = {
    "highway": 1.0,
    "city": 0.8,
    "mixed": 0.9,
    "offroad": 0.6,
    "heavy_traffic": 0.7,
}


class MaintenanceScheduler:
    """Heuristic-based scheduling for vehicle maintenance."""

    @staticmethod
    def calculate_optimal_service_date(vehicle_stats: dict) -> dict:
        """
        Recommend an optimal service window based on vehicle usage.

        Args:
            vehicle_stats: dict with keys:
                - mileage (float): current odometer reading
                - last_service_date (str or datetime): ISO date or datetime obj
                - engine_hours (float): total engine hours
                - driving_conditions (str): one of highway/city/mixed/offroad/heavy_traffic

        Returns:
            dict with service_date, urgency, reason, days_until_service.
        """
        mileage = float(vehicle_stats.get("mileage", 0))
        last_service = vehicle_stats.get("last_service_date")
        float(vehicle_stats.get("engine_hours", 0))
        conditions = str(vehicle_stats.get("driving_conditions", "mixed")).lower()

        # Parse last service date
        if isinstance(last_service, str):
            last_service_dt = datetime.date.fromisoformat(last_service)
        elif isinstance(last_service, datetime.datetime):
            last_service_dt = last_service.date()
        elif isinstance(last_service, datetime.date):
            last_service_dt = last_service
        else:
            last_service_dt = datetime.date.today() - datetime.timedelta(days=180)

        today = datetime.date.today()
        days_since_service = (today - last_service_dt).days
        multiplier = _CONDITION_MULTIPLIERS.get(conditions, 0.9)

        # Heuristic: service every 5000 miles or 180 days, adjusted by conditions
        effective_mileage = mileage * multiplier
        mileage_ratio = effective_mileage / 5000.0
        days_ratio = days_since_service / 180.0

        # Combined urgency score (0 = just serviced, 1+ = overdue)
        urgency_score = max(mileage_ratio, days_ratio)

        if urgency_score >= 1.5:
            urgency = "High"
            days_to_service = 0
            reason = (
                f"Vehicle is {urgency_score - 1:.0%} past the recommended service "
                f"interval ({mileage:.0f} mi / {days_since_service} days)."
            )
        elif urgency_score >= 1.0:
            urgency = "Medium"
            days_to_service = 14
            reason = (
                f"Service is due soon ({mileage:.0f} mi / "
                f"{days_since_service} days since last service)."
            )
        else:
            urgency = "Low"
            days_to_service = max(30, int(30 * (1 - urgency_score)))
            reason = "Within normal operating range; routine service recommended."

        # Build recommended date
        service_date = today + datetime.timedelta(days=days_to_service)

        return {
            "service_date": service_date.isoformat(),
            "urgency": urgency,
            "reason": reason,
            "days_until_service": days_to_service,
            "current_mileage": mileage,
            "days_since_last_service": days_since_service,
            "driving_conditions": conditions,
        }

    @staticmethod
    def estimate_part_lifespan(part_type: str, usage_stats: dict) -> dict:
        """
        Estimate remaining life for a vehicle part.

        Args:
            part_type: one of brakes, tires, battery, oil, coolant.
            usage_stats: dict with optional keys:
                - mileage (float): current mileage
                - current_mileage_on_part (float): miles since part was installed
                - days_on_part (int): days since part was installed
                - sensor_trend (str): one of normal, degrading, critical

        Returns:
            dict with remaining_miles, remaining_days, remaining_pct, status, reason.
        """
        part = _PART_LIFESPAN_ESTIMATES.get(part_type)
        if part is None:
            valid = list(_PART_LIFESPAN_ESTIMATES.keys())
            return {"error": f"Unknown part '{part_type}'. Valid: {valid}"}

        mileage = float(usage_stats.get("mileage", 0))
        miles_on_part = float(usage_stats.get("current_mileage_on_part", mileage))
        days_on_part = int(usage_stats.get("days_on_part", 0))
        sensor_trend = str(usage_stats.get("sensor_trend", "normal")).lower()

        # Calculate remaining percentages
        miles_remaining = max(0, part["mileage_max"] - miles_on_part)
        days_remaining = max(0, part["days_max"] - days_on_part)
        miles_pct = min(100, miles_on_part / part["mileage_max"] * 100)
        days_pct = min(100, days_on_part / part["days_max"] * 100)
        remaining_pct = 100 - max(miles_pct, days_pct)

        # Sensor trend adjustment
        trend_penalty = {"normal": 0.0, "degrading": -15.0, "critical": -30.0}
        remaining_pct += trend_penalty.get(sensor_trend, 0.0)
        remaining_pct = max(0.0, min(100.0, remaining_pct))

        # Determine status
        if remaining_pct <= 10:
            status = "Critical"
            reason = (
                f"{part['label']} is near end of life ({remaining_pct:.0f}% remaining)."
            )
        elif remaining_pct <= 30:
            status = "Replace Soon"
            reason = f"{part['label']} should be replaced soon ({remaining_pct:.0f}% remaining)."
        elif remaining_pct <= 50:
            status = "Monitor"
            reason = (
                f"{part['label']} has moderate wear ({remaining_pct:.0f}% remaining)."
            )
        else:
            status = "Good"
            reason = f"{part['label']} has plenty of life left ({remaining_pct:.0f}% remaining)."

        return {
            "part": part_type,
            "label": part["label"],
            "remaining_pct": round(remaining_pct, 1),
            "remaining_miles": max(0, int(miles_remaining)),
            "remaining_days": max(0, int(days_remaining)),
            "status": status,
            "reason": reason,
            "sensor_trend": sensor_trend,
        }

    @staticmethod
    def prioritize_services(pending_services: list[dict]) -> list[dict]:
        """
        Rank pending services by urgency using configured service windows.

        Each item should have at least an ``urgency`` field
        (one of ``"High"``, ``"Medium"``, ``"Low"``).

        Args:
            pending_services: list of service dicts.

        Returns:
            Same list sorted by urgency then by a secondary sort key if present.
        """
        urgency_rank = {"High": 0, "Medium": 1, "Low": 2}

        def sort_key(svc: dict[str, Any]) -> tuple:
            urgency = svc.get("urgency", "Low")
            rank = urgency_rank.get(urgency, 99)
            # Negative days_until_service = overdue → sort first within urgency band
            days = -svc.get("days_until_service", 999)
            return rank, days

        ranked = sorted(pending_services, key=sort_key)

        # Annotate each with the assigned window (days)
        for item in ranked:
            urgency = item.get("urgency", "Low")
            item["service_window_days"] = PRIORITY_SERVICE_WINDOWS.get(urgency, 30)

        return ranked
