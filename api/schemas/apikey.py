"""
API Key schemas for request/response validation.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Human-readable name for the key"
    )
    scopes: list[str] = Field(
        default=["read"], description="List of scopes/permissions"
    )
    expires_days: int | None = Field(
        None, ge=1, le=3650, description="Optional expiry in days"
    )


class APIKeyResponse(BaseModel):
    """API key response (without full key except on creation)."""

    id: int
    name: str
    prefix: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool = True
    key: str | None = Field(None, description="Full key - only returned on creation")

    model_config = {"from_attributes": True}


class APIKeyListResponse(BaseModel):
    """Paginated list of API keys."""

    items: list[APIKeyResponse]


class StatusResponse(BaseModel):
    """Generic status response."""

    status: str
    detail: str | None = None
