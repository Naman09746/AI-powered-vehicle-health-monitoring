"""
Threshold-based alert engine.
Generates alerts from sensor readings, predictions, and vehicle service history.
Fires webhooks for triggered alerts.
"""

import datetime

import core.db as database
from core.config import ALERT_RULES


def check_and_generate_alerts(
    sensor_data: dict,
    vehicle_id: int,
    user_id: int,
    failure_prob: float | None = None,
    vehicle_info: dict | None = None,
) -> list[dict]:
    """
    Check all alert rules against current sensor data and generate alerts.

    Args:
        sensor_data: Dict of current sensor values.
        vehicle_id: Vehicle ID.
        user_id: User ID.
        failure_prob: Optional failure probability from model.
        vehicle_info: Optional vehicle info dict (for maintenance overdue checks).

    Returns:
        List of generated alert dicts.
    """
    generated = []

    for alert_name, rule in ALERT_RULES.items():
        triggered = False
        value = None

        if rule["condition"] == "above":
            value = sensor_data.get(rule["sensor"])
            if value is not None and value > rule["threshold"]:
                triggered = True
        elif rule["condition"] == "below":
            value = sensor_data.get(rule["sensor"])
            if value is not None and value < rule["threshold"]:
                triggered = True
        elif rule["condition"] == "failure_prob_above":
            if failure_prob is not None and failure_prob > rule["threshold"]:
                triggered = True
                value = failure_prob

        if triggered:
            message = rule["message"].format(value=value)
            alert = database.create_alert(
                vehicle_id=vehicle_id,
                user_id=user_id,
                alert_type=alert_name,
                severity=rule["severity"],
                message=message,
                sensor_value=value,
            )
            if alert:  # None means deduplicated (already fired recently)
                generated.append(
                    {
                        "id": alert.id,
                        "type": alert_name,
                        "severity": rule["severity"],
                        "message": message,
                        "created_at": alert.created_at,
                    }
                )

                # ── Fire webhook asynchronously ──
                _fire_alert_webhook(alert_name, rule, alert, vehicle_id, user_id, value)

    # Check maintenance overdue
    if vehicle_info:
        overdue_alert = _check_maintenance_overdue(vehicle_info, vehicle_id, user_id)
        if overdue_alert:
            generated.append(overdue_alert)

    return generated


def _check_maintenance_overdue(
    vehicle_info: dict, vehicle_id: int, user_id: int
) -> dict | None:
    """Check if maintenance is overdue based on last service date and mileage."""
    last_service = vehicle_info.get("last_service_date")
    vehicle_info.get("mileage", 0)

    if last_service:
        if isinstance(last_service, str):
            try:
                last_service = datetime.date.fromisoformat(last_service)
            except ValueError:
                return None

        days_since_service = (datetime.date.today() - last_service).days

        # Alert if >180 days since last service or mileage > 10000 since
        if days_since_service > 180:
            message = (
                f"Maintenance overdue! Last service was {days_since_service} days ago."
            )
            alert = database.create_alert(
                vehicle_id=vehicle_id,
                user_id=user_id,
                alert_type="maintenance_overdue",
                severity="Medium",
                message=message,
                sensor_value=float(days_since_service),
            )
            if alert:
                return {
                    "id": alert.id,
                    "type": "maintenance_overdue",
                    "severity": "Medium",
                    "message": message,
                    "created_at": alert.created_at,
                }

    return None


def _fire_alert_webhook(
    alert_name: str,
    rule: dict,
    alert,
    vehicle_id: int,
    user_id: int,
    value: float | None,
) -> None:
    """Fire a webhook for a triggered alert (runs in background)."""
    try:
        import asyncio

        from api.webhooks import dispatch_webhook

        # Try to fire asynchronously if an event loop is running
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop (e.g., called from Streamlit sync context) — skip async dispatch
            return

        asyncio.ensure_future(
            dispatch_webhook(
                event="alert.fired",
                payload={
                    "alert_id": alert.id,
                    "alert_type": alert_name,
                    "severity": rule["severity"],
                    "message": rule["message"].format(value=value)
                    if value
                    else rule["message"],
                    "sensor": rule.get("sensor"),
                    "threshold": rule.get("threshold"),
                    "value": value,
                },
                user_id=user_id,
                vehicle_id=vehicle_id,
            )
        )
    except Exception:
        from core.logger import get_logger

        get_logger("alerts.webhook").exception("Failed to fire alert webhook")


def get_severity_icon(severity: str) -> str:
    """Get a compact severity label for alert displays."""
    return {
        "High": "HIGH",
        "Medium": "MED",
        "Low": "LOW",
    }.get(severity, "INFO")


def get_severity_color(severity: str) -> str:
    """Get a color for alert severity."""
    return {
        "High": "#dc2626",
        "Medium": "#d97706",
        "Low": "#2563eb",
    }.get(severity, "#6b7280")
