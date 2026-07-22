"""
Rule-based maintenance recommendation engine.
Maps predictions and sensor anomalies to specific maintenance actions.
"""

import datetime

from core.config import (
    PRIORITY_SERVICE_WINDOWS,
    RECOMMENDATION_RULES,
    SENSOR_THRESHOLDS,
)
from core.utils import get_priority


def get_recommendations(
    failure_prob: float,
    sensor_data: dict | None = None,
    vehicle_info: dict | None = None,
) -> list[dict]:
    """
    Generate maintenance recommendations based on prediction and sensor anomalies.

    Args:
        failure_prob: Failure probability from the model (0-1).
        sensor_data: Dict of latest sensor values.
        vehicle_info: Dict with vehicle details (last_service_date, mileage, etc.).

    Returns:
        List of recommendation dicts, sorted by priority (highest first).
    """
    recommendations = []
    priority = get_priority(failure_prob)

    if sensor_data:
        for sensor, rule in RECOMMENDATION_RULES.items():
            value = sensor_data.get(sensor)
            if value is None:
                continue

            thresholds = SENSOR_THRESHOLDS.get(sensor, {})
            is_anomalous = False

            if (
                rule["condition"] == "high"
                and value > thresholds.get("max", float("inf"))
                or rule["condition"] == "low"
                and value < thresholds.get("min", float("-inf"))
            ):
                is_anomalous = True

            if is_anomalous:
                sensor_priority = _escalate_priority(priority, value, thresholds)
                rec_date = _compute_recommended_date(sensor_priority, vehicle_info)
                recommendations.append(
                    {
                        "sensor": sensor,
                        "sensor_label": thresholds.get("label", sensor),
                        "action": rule["action"],
                        "description": rule["description"],
                        "priority": sensor_priority,
                        "priority_color": _priority_color(sensor_priority),
                        "current_value": f"{value:.1f} {thresholds.get('unit', '')}",
                        "normal_range": f"{thresholds.get('min', '?')}–{thresholds.get('max', '?')} {thresholds.get('unit', '')}",
                        "recommended_date": rec_date,
                    }
                )

    # If high failure risk but no specific sensor triggered, add general recommendation
    if failure_prob >= 0.7 and not recommendations:
        recommendations.append(
            {
                "sensor": "general",
                "sensor_label": "Overall System",
                "action": "Comprehensive vehicle inspection recommended",
                "description": "Model indicates high failure risk. A full diagnostic check is advised.",
                "priority": "High",
                "priority_color": "#FF4444",
                "current_value": f"Failure probability: {failure_prob:.0%}",
                "normal_range": "N/A",
                "recommended_date": datetime.date.today().isoformat(),
            }
        )
    elif failure_prob >= 0.4 and not recommendations:
        recommendations.append(
            {
                "sensor": "general",
                "sensor_label": "Overall System",
                "action": "Preventive maintenance check recommended",
                "description": "Model indicates moderate failure risk. Schedule a routine check-up.",
                "priority": "Medium",
                "priority_color": "#FFBB33",
                "current_value": f"Failure probability: {failure_prob:.0%}",
                "normal_range": "N/A",
                "recommended_date": _compute_recommended_date("Medium", vehicle_info),
            }
        )

    # Sort by priority (High first)
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))

    return recommendations


def _escalate_priority(base_priority: str, value: float, thresholds: dict) -> str:
    """Escalate priority if sensor is in critical range."""
    critical_min = thresholds.get("critical_min", float("-inf"))
    critical_max = thresholds.get("critical_max", float("inf"))

    if value <= critical_min or value >= critical_max:
        return "High"

    return base_priority


def _compute_recommended_date(priority: str, vehicle_info: dict | None) -> str:
    """Compute a recommended service date based on priority and last service."""
    days_offset = PRIORITY_SERVICE_WINDOWS.get(priority, 30)

    if days_offset == 0:
        return datetime.date.today().isoformat()

    base_date = datetime.date.today()
    if vehicle_info and vehicle_info.get("last_service_date"):
        try:
            last_service = vehicle_info["last_service_date"]
            if isinstance(last_service, str):
                last_service = datetime.date.fromisoformat(last_service)
            base_date = max(base_date, last_service)
        except (ValueError, TypeError):
            pass

    return (base_date + datetime.timedelta(days=days_offset)).isoformat()


def _priority_color(priority: str) -> str:
    """Get color for priority level."""
    return {
        "High": "#FF4444",
        "Medium": "#FFBB33",
        "Low": "#00C851",
    }.get(priority, "#999999")
