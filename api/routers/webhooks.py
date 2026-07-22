"""
Webhook subscription management router.

Allows users to subscribe to async events (predictions, alerts, training, etc.).
"""

from __future__ import annotations

import json
from datetime import datetime
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1, max_length=500)
    secret: str | None = Field(None, max_length=500)
    events: list[str] = Field(default=["*"], description="Event types or ['*'] for all")
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=10, ge=1, le=60)


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    retry_count: int | None = Field(None, ge=0, le=10)
    timeout_seconds: int | None = Field(None, ge=1, le=60)


class WebhookResponse(BaseModel):
    id: int
    name: str
    url: str
    events: list[str]
    is_active: bool
    retry_count: int
    timeout_seconds: int
    last_triggered_at: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class WebhookListResponse(BaseModel):
    items: list[WebhookResponse]


class WebhookTestResponse(BaseModel):
    status: str
    status_code: int | None = None
    response_body: str | None = None


class WebhookTestCreate(BaseModel):
    """Schema for testing a webhook delivery without a saved subscription."""

    url: str = Field(..., description="Target URL to send the test event to")
    secret: str | None = Field(
        None, description="HMAC signing secret (uses app default if omitted)"
    )
    event: str = Field(
        default="prediction.complete", description="Event type to simulate"
    )
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    payload_override: dict[str, Any] | None = Field(
        None, description="Optional custom payload data"
    )


@router.post("/test", response_model=WebhookTestResponse)
async def test_webhook_delivery(
    body: WebhookTestCreate,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Send a test webhook event to an arbitrary URL.

    Unlike ``POST /{webhook_id}/test``, this endpoint does **not** require
    a saved subscription — you provide the URL, secret, and event type
    directly.  Useful for debugging and initial setup.
    """
    from api.webhooks import WebhookEvent, WebhookPayload, deliver_webhook

    # Validate event type
    try:
        event = WebhookEvent(body.event)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event '{body.event}'. Valid events: {[e.value for e in WebhookEvent]}",
        )

    payload = WebhookPayload(
        event=event,
        vehicle_id=None,
        user_id=user["id"],
        data=body.payload_override
        or {
            "test": True,
            "message": "This is a test webhook event triggered by the user.",
            "source": "api.test_endpoint",
        },
    )

    from core.config import SECRET_KEY

    secret = body.secret or SECRET_KEY
    status_code, response_body = await deliver_webhook(
        body.url,
        payload,
        secret,
        timeout=body.timeout_seconds,
    )

    return WebhookTestResponse(
        status="delivered" if status_code and 200 <= status_code < 300 else "failed",
        status_code=status_code or 0,
        response_body=response_body,
    )


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(user: dict[str, Any] = Depends(get_current_user)):
    """List all webhook subscriptions for the current user."""
    import core.db as database
    from core.db import WebhookSubscription

    session = database.get_session()
    try:
        subscriptions = (
            session.query(WebhookSubscription)
            .filter_by(user_id=user["id"])
            .order_by(WebhookSubscription.created_at.desc())
            .all()
        )

        return WebhookListResponse(items=[_to_response(s) for s in subscriptions])
    finally:
        session.close()


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate, user: dict[str, Any] = Depends(get_current_user)
):
    """Create a new webhook subscription."""
    import core.db as database
    from core.db import WebhookSubscription

    session = database.get_session()
    try:
        sub = WebhookSubscription(
            user_id=user["id"],
            name=body.name,
            url=body.url,
            secret=body.secret or "",
            events=json.dumps(body.events),
            retry_count=body.retry_count,
            timeout_seconds=body.timeout_seconds,
        )
        session.add(sub)
        session.commit()
        session.refresh(sub)
        return _to_response(sub)
    finally:
        session.close()


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: int, user: dict[str, Any] = Depends(get_current_user)
):
    """Get a specific webhook subscription."""
    import core.db as database
    from core.db import WebhookSubscription

    session = database.get_session()
    try:
        sub = (
            session.query(WebhookSubscription)
            .filter_by(id=webhook_id, user_id=user["id"])
            .first()
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return _to_response(sub)
    finally:
        session.close()


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    body: WebhookUpdate,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Update a webhook subscription."""
    import core.db as database
    from core.db import WebhookSubscription

    session = database.get_session()
    try:
        sub = (
            session.query(WebhookSubscription)
            .filter_by(id=webhook_id, user_id=user["id"])
            .first()
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Webhook not found")

        if body.name is not None:
            sub.name = body.name
        if body.url is not None:
            sub.url = body.url
        if body.secret is not None:
            sub.secret = body.secret
        if body.events is not None:
            sub.events = json.dumps(body.events)
        if body.is_active is not None:
            sub.is_active = body.is_active
        if body.retry_count is not None:
            sub.retry_count = body.retry_count
        if body.timeout_seconds is not None:
            sub.timeout_seconds = body.timeout_seconds

        sub.updated_at = datetime.now(UTC)
        session.commit()
        session.refresh(sub)
        return _to_response(sub)
    finally:
        session.close()


@router.delete("/{webhook_id}", response_model=dict)
async def delete_webhook(
    webhook_id: int, user: dict[str, Any] = Depends(get_current_user)
):
    """Delete a webhook subscription."""
    import core.db as database
    from core.db import WebhookSubscription

    session = database.get_session()
    try:
        sub = (
            session.query(WebhookSubscription)
            .filter_by(id=webhook_id, user_id=user["id"])
            .first()
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Webhook not found")

        session.delete(sub)
        session.commit()
        return {"status": "ok", "detail": "Webhook deleted"}
    finally:
        session.close()


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: int, user: dict[str, Any] = Depends(get_current_user)
):
    """Send a test event to a webhook subscription."""
    import core.db as database
    from api.webhooks import WebhookEvent, WebhookPayload, deliver_webhook
    from core.db import WebhookSubscription

    session = database.get_session()
    try:
        sub = (
            session.query(WebhookSubscription)
            .filter_by(id=webhook_id, user_id=user["id"])
            .first()
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Webhook not found")

        payload = WebhookPayload(
            event=WebhookEvent.PREDICTION_COMPLETE,
            vehicle_id=None,
            user_id=user["id"],
            data={"test": True, "message": "This is a test webhook event"},
        )

        from core.config import SECRET_KEY

        status_code, response_body = await deliver_webhook(
            sub.url,
            payload,
            sub.secret or SECRET_KEY,
            timeout=sub.timeout_seconds,
        )

        return WebhookTestResponse(
            status="delivered"
            if status_code and 200 <= status_code < 300
            else "failed",
            status_code=status_code or 0,
            response_body=response_body,
        )
    finally:
        session.close()


def _to_response(sub) -> WebhookResponse:
    """Convert DB model to response schema."""
    return WebhookResponse(
        id=sub.id,
        name=sub.name,
        url=sub.url,
        events=json.loads(sub.events) if sub.events else ["*"],
        is_active=sub.is_active,
        retry_count=sub.retry_count or 3,
        timeout_seconds=sub.timeout_seconds or 10,
        last_triggered_at=sub.last_triggered_at.isoformat()
        if sub.last_triggered_at
        else None,
        created_at=sub.created_at.isoformat() if sub.created_at else "",
        updated_at=sub.updated_at.isoformat() if sub.updated_at else "",
    )
