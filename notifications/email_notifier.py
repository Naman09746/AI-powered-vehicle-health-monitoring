"""
Email alert delivery via SMTP (Gmail App Password or any SMTP relay).

Sends formatted HTML emails with:
- Alert severity badge
- Vehicle name + current sensor readings
- Recommended action + dashboard deep-link
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from core.config import EMAIL_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from core.logger import get_logger

log = get_logger("email_notifier")


def send_alert_email(
    user_email: str, alert: dict[str, Any], vehicle_info: dict[str, Any] | None = None
) -> bool:
    """
    Send a formatted alert notification email.

    Args:
        user_email: Recipient email address.
        alert: Dict with keys ``type``, ``severity``, ``message``, ``created_at``.
        vehicle_info: Optional dict with ``vehicle_id_display``, ``model``.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        log.warning("SMTP not configured — skipping email to %s", user_email)
        return False

    vehicle_name = "Unknown"
    if vehicle_info:
        vehicle_name = vehicle_info.get("vehicle_id_display", "Unknown")

    severity = alert.get("severity", "INFO").upper()
    severity_colors = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#2563eb"}
    color = severity_colors.get(severity, "#6b7280")

    html = f"""\
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<div style="border-left:4px solid {color};padding:16px;background:#f9fafb;">
<div style="font-size:12px;color:#666;">VEHICLE HEALTH MONITOR — ALERT</div>
<h2 style="margin:8px 0;color:{color};">{severity} — {alert.get("type", "Alert")}</h2>
<p style="font-size:16px;">{alert.get("message", "")}</p>
<table style="margin:16px 0;border-collapse:collapse;">
<tr><td style="padding:4px 12px 4px 0;color:#666;">Vehicle</td>
    <td style="font-weight:600;">{vehicle_name}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Severity</td>
    <td style="font-weight:600;color:{color};">{severity}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Time</td>
    <td style="font-weight:600;">{alert.get("created_at", "")}</td></tr>
</table>
<a href="http://localhost:8501/Recommendations"
   style="display:inline-block;padding:10px 20px;background:{color};color:white;
          text-decoration:none;border-radius:6px;">View in Dashboard</a>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{severity}] Vehicle Alert — {vehicle_name}"
    msg["From"] = EMAIL_FROM
    msg["To"] = user_email
    msg.attach(MIMEText(html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [user_email], msg.as_string())
        log.info("Alert email sent to %s", user_email)
        return True
    except Exception as exc:
        log.error("Failed to send email to %s: %s", user_email, exc)
        return False


def send_daily_fleet_digest(user_email: str, fleet_summary: dict[str, Any]) -> bool:
    """Send a daily fleet health digest email."""
    if not SMTP_USER or not SMTP_PASSWORD:
        return False

    html = f"""\
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2>Daily Fleet Digest</h2>
<p>Average fleet health: <strong>{fleet_summary.get("avg_score", "N/A")}</strong></p>
<p>Healthy: {fleet_summary.get("healthy_count", 0)} | "
   f"At Risk: {fleet_summary.get("at_risk_count", 0)} | "
   f"Critical: {fleet_summary.get("critical_count", 0)}</p>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Fleet Digest — Vehicle Health Monitor"
    msg["From"] = EMAIL_FROM
    msg["To"] = user_email
    msg.attach(MIMEText(html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [user_email], msg.as_string())
        return True
    except Exception as exc:
        log.error("Digest email failed: %s", exc)
        return False
