"""
Webhook system for async event delivery.

Supports:
- Event types: prediction.complete, alert.fired, training.done, drift.detected
- HMAC-SHA256 signature verification
- Retry with exponential backoff (3 retries by default)
- Delivery logging to WebhookLog table
- Dispatch as FastAPI BackgroundTasks
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from core.config import SECRET_KEY
from core.logger import get_logger

log = get_logger("webhooks")


class WebhookEvent(StrEnum):
    """Supported webhook event types."""

    PREDICTION_COMPLETE = "prediction.complete"
    ALERT_FIRED = "alert.fired"
    TRAINING_DONE = "training.done"
    DRIFT_DETECTED = "drift.detected"
    RETRAIN_FAILED = "retrain.failed"
    VEHICLE_CREATED = "vehicle.created"
    VEHICLE_DELETED = "vehicle.deleted"


class WebhookPayload(BaseModel):
    """Standard webhook event payload."""

    event: WebhookEvent
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    vehicle_id: int | None = None
    user_id: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None

    model_config = {"use_enum_values": True}


class WebhookDelivery(BaseModel):
    """Webhook delivery record."""

    id: int | None = None
    webhook_id: int
    event: WebhookEvent
    url: str
    payload: dict[str, Any]
    status: str  # pending, delivered, failed
    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None
    attempt: int = 1
    delivered_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"use_enum_values": True}


# ── HMAC signing ──────────────────────────────────────────────────


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    """Sign webhook payload with HMAC-SHA256.

    Args:
        payload: The JSON-serialisable payload dict to sign.
        secret: The shared secret key.

    Returns:
        Hex-encoded HMAC-SHA256 signature.
    """
    body = json.dumps(payload, separators=(",", ":"), default=str).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_webhook_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Verify incoming webhook signature (for outgoing webhooks from other services).

    Args:
        payload_body: Raw request body bytes.
        signature: The ``X-Webhook-Signature`` header value.
        secret: The shared secret key.

    Returns:
        ``True`` if the signature matches.
    """
    expected = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Single delivery ───────────────────────────────────────────────


async def send_webhook(
    url: str,
    payload: WebhookPayload,
    secret: str,
    timeout: int = 10,
    max_retries: int = 3,
) -> tuple[int, str]:
    """Send a webhook event to a URL with HMAC signing and retry logic.

    Implements exponential backoff: 1s, 2s, 4s between retries.

    Args:
        url: Target URL for the webhook.
        payload: The ``WebhookPayload`` to deliver.
        secret: HMAC signing secret.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of delivery attempts.

    Returns:
        Tuple of ``(status_code, response_body)`` where ``status_code``
        is ``0`` if the request could not be made (network error, timeout).
    """
    # Sign payload
    payload_dict = payload.model_dump(exclude={"signature"}, mode="json")
    payload_dict["signature"] = sign_payload(payload_dict, secret)

    last_status: int = 0
    last_body: str = ""

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json=payload_dict,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Event": payload.event.value,
                        "X-Webhook-Signature": payload_dict["signature"],
                        "X-Webhook-Attempt": str(attempt),
                        "User-Agent": "VehicleHealth-Webhook/1.0",
                    },
                )
                last_status = response.status_code
                last_body = response.text[:1000]

                # 2xx is success — stop retrying
                if 200 <= response.status_code < 300:
                    log.info(
                        "Webhook delivered (attempt %d/%d): %s -> %d",
                        attempt,
                        max_retries,
                        url,
                        response.status_code,
                    )
                    return last_status, last_body

                # Non-2xx — log and retry if not a client error (4xx that isn't 429)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    log.warning(
                        "Webhook rejected (attempt %d/%d): %s -> %d (not retrying client error)",
                        attempt,
                        max_retries,
                        url,
                        response.status_code,
                    )
                    return last_status, last_body

                log.warning(
                    "Webhook attempt %d/%d failed: %s -> %d",
                    attempt,
                    max_retries,
                    url,
                    response.status_code,
                )

        except httpx.TimeoutException:
            last_status = 0
            last_body = "timeout"
            log.warning(
                "Webhook timeout (attempt %d/%d): %s",
                attempt,
                max_retries,
                url,
            )
        except httpx.RequestError as e:
            last_status = 0
            last_body = str(e)[:500]
            log.warning(
                "Webhook request error (attempt %d/%d): %s - %s",
                attempt,
                max_retries,
                url,
                str(e),
            )

        # Exponential backoff (1s, 2s, 4s) — skip on last attempt
        if attempt < max_retries:
            backoff = 2 ** (attempt - 1)
            await asyncio.sleep(backoff)

    log.error("Webhook delivery failed after %d attempts: %s", max_retries, url)
    return last_status, last_body


# ── Dispatch to all subscribers ───────────────────────────────────


async def dispatch_webhook(
    event: str | WebhookEvent,
    payload: dict[str, Any],
    user_id: int | None = None,
    vehicle_id: int | None = None,
) -> list[WebhookDelivery]:
    """Dispatch a webhook event to all active subscriptions.

    Looks up the user's active webhook subscriptions matching the event,
    delivers the event to each matching endpoint with retry logic, and
    logs delivery results to the ``WebhookLog`` table.

    This function is designed to be called from:
    - ML training completion (``api/routers/ml.py``)
    - Prediction completion (``api/routers/predictions.py``)
    - Alert creation (``alerts.py`` ``create_alert()``)

    Usage from a FastAPI endpoint with ``BackgroundTasks``::

        from fastapi import BackgroundTasks

        @router.post("/train/{vehicle_id}")
        async def train(
            vehicle_id: int,
            background_tasks: BackgroundTasks,
            user: dict = Depends(get_current_user),
        ):
            result = ...
            background_tasks.add_task(
                dispatch_webhook,
                event="training.done",
                payload={"vehicle_id": vehicle_id, "model_id": model_id},
                user_id=user["id"],
                vehicle_id=vehicle_id,
            )
            return result

    Args:
        event: Event type string (e.g. ``"prediction.complete"``) or
               ``WebhookEvent`` enum member.
        payload: Arbitrary JSON-serialisable data dict to send.
        user_id: The user whose subscriptions to check.  If ``None``,
                 all active subscriptions for the event are used.
        vehicle_id: Optional vehicle context for the event.

    Returns:
        List of ``WebhookDelivery`` records (one per subscription).
    """
    import core.db as database
    from core.db import WebhookSubscription as WebhookModel

    # Normalise event to string
    event_str = event.value if isinstance(event, WebhookEvent) else event

    deliveries: list[WebhookDelivery] = []

    session = database.get_session()
    try:
        # Query active webhooks
        query = session.query(WebhookModel).filter_by(is_active=True)

        if user_id is not None:
            query = query.filter_by(user_id=user_id)

        subscriptions = query.all()

        if not subscriptions:
            log.debug(
                "No active webhook subscriptions for event=%s user=%s",
                event_str,
                user_id,
            )
            return deliveries

        for sub in subscriptions:
            # Check event filter
            if sub.events:
                try:
                    subscribed_events = json.loads(sub.events)
                    if (
                        event_str not in subscribed_events
                        and "*" not in subscribed_events
                    ):
                        continue
                except (json.JSONDecodeError, TypeError):
                    log.warning("Invalid events JSON for webhook %d", sub.id)
                    continue

            wpe = WebhookEvent(event_str) if isinstance(event, str) else event
            wh_payload = WebhookPayload(
                event=wpe,
                vehicle_id=vehicle_id,
                user_id=sub.user_id,
                data=payload,
            )

            secret = sub.secret or SECRET_KEY
            status_code, response_body = await send_webhook(
                url=sub.url,
                payload=wh_payload,
                secret=secret,
                timeout=sub.timeout_seconds or 10,
                max_retries=sub.retry_count or 3,
            )

            # Determine final status
            if status_code and 200 <= status_code < 300:
                status = "delivered"
                delivered_at = datetime.now(UTC)
            else:
                status = "failed"
                delivered_at = None

            # Build delivery log record
            delivery = WebhookDelivery(
                webhook_id=sub.id,
                event=wpe,
                url=sub.url,
                payload=wh_payload.model_dump(mode="json"),
                status=status,
                status_code=status_code or 0,
                response_body=response_body,
                error=None if status == "delivered" else response_body,
                attempt=sub.retry_count or 3,
                delivered_at=delivered_at,
            )

            # Persist delivery log
            _log_delivery_to_db(session, sub.id, delivery, wpe)

            # Update last_triggered_at
            sub.last_triggered_at = datetime.now(UTC)

            deliveries.append(delivery)

            log.info(
                "Webhook dispatch %s: %s -> %s (status=%s, code=%d)",
                sub.id,
                event_str,
                sub.url,
                status,
                status_code or 0,
            )

        session.commit()

    except Exception:
        session.rollback()
        log.exception("Error dispatching webhook event=%s", event_str)
    finally:
        session.close()

    return deliveries


# ── Legacy helpers (preserved for backward compatibility) ─────────


async def deliver_webhook(
    url: str,
    payload: WebhookPayload,
    secret: str,
    timeout: int = 10,
) -> tuple[int, str]:
    """
    Deliver a webhook event to a URL.

    This is a single-attempt version — for production use with retries,
    prefer ``send_webhook()``.

    Returns:
        Tuple of (status_code, response_body)
    """
    # Sign payload
    payload_dict = payload.model_dump(exclude={"signature"}, mode="json")
    payload_dict["signature"] = sign_payload(payload_dict, secret)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json=payload_dict,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Event": payload.event.value,
                    "X-Webhook-Signature": payload_dict["signature"],
                    "User-Agent": "VehicleHealth-Webhook/1.0",
                },
            )
            return response.status_code, response.text[:1000]
    except httpx.TimeoutException:
        log.warning("Webhook delivery timeout: %s", url)
        return 0, "timeout"
    except httpx.RequestError as e:
        log.warning("Webhook delivery failed: %s - %s", url, str(e))
        return 0, str(e)[:500]


async def fire_webhook_event(
    webhook_id: int,
    url: str,
    secret: str,
    event: WebhookEvent,
    vehicle_id: int | None = None,
    user_id: int | None = None,
    data: dict[str, Any] | None = None,
) -> WebhookDelivery:
    """Fire a webhook event to a specific webhook endpoint."""
    payload = WebhookPayload(
        event=event,
        vehicle_id=vehicle_id,
        user_id=user_id,
        data=data or {},
    )

    status_code, response_body = await deliver_webhook(url, payload, secret)

    delivery = WebhookDelivery(
        webhook_id=webhook_id,
        event=event,
        url=url,
        payload=payload.model_dump(mode="json"),
        status="delivered" if status_code and 200 <= status_code < 300 else "failed",
        status_code=status_code or 0,
        response_body=response_body,
        delivered_at=datetime.now(UTC) if status_code else None,
    )

    log.info(
        "Webhook delivery %s: %s -> %d",
        delivery.status,
        event.value,
        status_code or 0,
    )

    return delivery


async def fire_event_to_all_subscribers(
    event: WebhookEvent,
    vehicle_id: int | None = None,
    user_id: int | None = None,
    data: dict[str, Any] | None = None,
) -> list[WebhookDelivery]:
    """
    Fire a webhook event to all subscribed endpoints.

    Looks up webhook subscriptions from the database and delivers
    the event to all matching endpoints.

    .. deprecated::
        Use ``dispatch_webhook()`` instead for production use.
    """
    import core.db as database

    deliveries: list[WebhookDelivery] = []

    session = database.get_session()
    try:
        from core.db import WebhookSubscription as WebhookModel

        query = session.query(WebhookModel).filter_by(is_active=True)

        if user_id:
            query = query.filter_by(user_id=user_id)

        subscriptions = query.all()

        for sub in subscriptions:
            if sub.events:
                try:
                    subscribed_events = json.loads(sub.events)
                    if (
                        event.value not in subscribed_events
                        and "*" not in subscribed_events
                    ):
                        continue
                except Exception:
                    continue

            delivery = await fire_webhook_event(
                webhook_id=sub.id,
                url=sub.url,
                secret=sub.secret or SECRET_KEY,
                event=event,
                vehicle_id=vehicle_id,
                user_id=user_id,
                data=data,
            )

            if delivery.status_code:
                _log_delivery_to_db(session, sub.id, delivery, event)

            deliveries.append(delivery)
    finally:
        session.close()

    return deliveries


def _log_delivery_to_db(
    session, webhook_id: int, delivery: WebhookDelivery, event: WebhookEvent | str
) -> None:
    """Log delivery attempt to database."""
    try:
        from core.db import WebhookLog

        event_str = event.value if isinstance(event, WebhookEvent) else event

        log_entry = WebhookLog(
            webhook_id=webhook_id,
            event=event_str,
            status=delivery.status,
            status_code=delivery.status_code,
            response_body=delivery.response_body,
            error=delivery.error,
            attempt=delivery.attempt,
        )
        session.add(log_entry)
    except Exception:
        log.exception("Failed to add webhook delivery log entry")
