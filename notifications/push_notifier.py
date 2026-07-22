"""
Browser Web Push notifications (stub — requires VAPID keys + pywebpush).

For production, install ``pywebpush`` and set VAPID keys in the .env.
The stub logs notifications when the library isn't available.
"""

from __future__ import annotations

import json
from typing import Any

from core.config import VAPID_CLAIM_EMAIL, VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY
from core.logger import get_logger

log = get_logger("push_notifier")

_HAS_PYWEBPUSH = False
try:
    from pywebpush import WebPushException, webpush

    _HAS_PYWEBPUSH = True
except ImportError:
    pass


def send_push_notification(subscription_info: dict, alert: dict[str, Any]) -> bool:
    """
    Send a Web Push notification to a subscribed browser.

    Args:
        subscription_info: Dict with ``endpoint``, ``keys`` (auth, p256dh).
        alert: Dict with ``type``, ``severity``, ``message``.

    Returns:
        True if sent, False on failure or if VAPID is unconfigured.
    """
    if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
        log.debug("VAPID keys not configured — push notification skipped")
        return False

    if not _HAS_PYWEBPUSH:
        log.debug("pywebpush not installed — push notification logged only")
        log.info(
            "PUSH NOTIFICATION: %s — %s", alert.get("severity"), alert.get("message")
        )
        return True  # silent success in dev

    payload = json.dumps(
        {
            "title": f"[{alert.get('severity', 'ALERT')}] Vehicle Alert",
            "body": alert.get("message", ""),
            "icon": "/favicon.ico",
            "badge": "/badge.png",
            "tag": alert.get("type", "alert"),
            "data": {"url": "http://localhost:8501/Recommendations"},
        }
    )

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{VAPID_CLAIM_EMAIL}"},
        )
        log.info("Push notification sent")
        return True
    except WebPushException as exc:
        log.warning("Push notification failed: %s", exc)
        if exc.response and exc.response.status_code == 410:
            log.info("Subscription expired — should remove from DB")
        return False
    except Exception as exc:
        log.error("Push notification error: %s", exc)
        return False
