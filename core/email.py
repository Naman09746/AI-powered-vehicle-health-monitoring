"""
Email delivery helper module.
Sends transactional emails (verification links, password reset links) via Resend API.
"""

from __future__ import annotations

import os
import urllib.request
import json
from core.logger import get_logger

log = get_logger("email")

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Sends an email via Resend API."""
    if not RESEND_API_KEY:
        log.info("[MOCK EMAIL] To: %s | Subject: %s | Content: %s", to_email, subject, html_content[:100])
        return True

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": "VehicleHealth <noreply@vehiclehealth.app>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status in (200, 201):
                log.info("Successfully sent email to %s", to_email)
                return True
        return False
    except Exception as exc:
        log.error("Failed to send email to %s: %s", to_email, exc)
        return False


def send_verification_email(to_email: str, token: str) -> bool:
    verify_url = f"{APP_BASE_URL}/verify-email?token={token}"
    html = f"""
    <h2>Verify your Vehicle Health Monitor account</h2>
    <p>Click the link below to verify your email address and activate full platform access:</p>
    <p><a href="{verify_url}" style="background-color:#0ea5e9;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">Verify Email Address</a></p>
    <p>Or copy this link: {verify_url}</p>
    """
    return send_email(to_email, "Verify Your Email - Vehicle Health Monitor", html)


def send_password_reset_email(to_email: str, token: str) -> bool:
    reset_url = f"{APP_BASE_URL}/reset-password?token={token}"
    html = f"""
    <h2>Reset your Password</h2>
    <p>You requested a password reset for your Vehicle Health Monitor account.</p>
    <p><a href="{reset_url}" style="background-color:#0ea5e9;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;">Reset Password</a></p>
    <p>This link expires in 60 minutes. If you did not request this, please ignore this email.</p>
    """
    return send_email(to_email, "Reset Password - Vehicle Health Monitor", html)
