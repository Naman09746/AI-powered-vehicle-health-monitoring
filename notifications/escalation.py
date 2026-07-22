"""
Alert escalation rules.

- Severity=High, unacknowledged for 15 min → escalate (email/SMS)
- 3+ High alerts in 1 hour for same vehicle → auto-create incident ticket

Usage:
    from notifications.escalation import check_escalation
    check_escalation(vehicle_id, user_id)
"""

from __future__ import annotations

from typing import Any

import core.db as database
from core.logger import get_logger, log_event

log = get_logger("escalation")


def check_escalation(vehicle_id: int, user_id: int) -> list[dict[str, Any]]:
    """
    Evaluate escalation rules for a vehicle.

    Returns a list of escalation actions taken (empty list if none needed).
    """
    actions: list[dict[str, Any]] = []

    # ── Rule 1: High alert unacknowledged for 15+ minutes ──
    pending = database.get_unacknowledged_high_alerts(
        user_id,
        vehicle_id,
        since_minutes=15,
    )
    if pending:
        log.info(
            "Escalation: %d high alerts unacknowledged for vehicle %s",
            len(pending),
            vehicle_id,
        )
        user = database.get_user_by_id(user_id)
        if user and user.email:
            from notifications.email_notifier import send_alert_email

            for alert in pending[:3]:  # limit to 3
                alert_dict = {
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "created_at": str(alert.created_at),
                }
                sent = send_alert_email(user.email, alert_dict)
                if sent:
                    actions.append(
                        {
                            "action": "email_escalation",
                            "alert_id": alert.id,
                            "severity": alert.severity,
                        }
                    )
                    log_event(
                        "alert-escalated",
                        vehicle_id=vehicle_id,
                        alert_id=alert.id,
                        method="email",
                    )

    # ── Rule 2: 3+ High alerts in 1 hour → create incident ──
    count = database.count_alerts_last_hour(vehicle_id, user_id)
    if count >= 3:
        alerts = database.get_active_alerts(user_id, vehicle_id)
        recent_high = [a for a in alerts if a.severity == "High"][:10]
        alert_ids = [a.id for a in recent_high]

        # Check if an open incident already exists for this vehicle
        existing_incidents = database.get_open_incidents(user_id)
        already_has = any(
            inc.vehicle_id == vehicle_id and inc.status == "open"
            for inc in existing_incidents
        )

        if not already_has:
            title = f"Multiple critical alerts for vehicle #{vehicle_id}"
            desc = f"{count} High-severity alerts in the last hour."
            inc = database.create_incident(
                vehicle_id=vehicle_id,
                user_id=user_id,
                title=title,
                description=desc,
                related_alert_ids=alert_ids,
            )
            if inc:
                actions.append(
                    {
                        "action": "incident_created",
                        "incident_id": inc.id,
                        "alert_count": count,
                    }
                )
                log_event(
                    "incident-created",
                    vehicle_id=vehicle_id,
                    incident_id=inc.id,
                    alert_count=count,
                )

    return actions
