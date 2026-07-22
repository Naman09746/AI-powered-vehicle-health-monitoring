"""
API Key management router.

Allows users to create, list, and revoke their own API keys.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

import core.db as database
from api.auth.apikey import generate_api_key, hash_api_key
from api.dependencies import get_current_user
from api.schemas.apikey import (
    APIKeyCreate,
    APIKeyListResponse,
    APIKeyResponse,
    StatusResponse,
)

router = APIRouter(prefix="/api/v1/auth/api-keys", tags=["auth", "api-keys"])


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(user: dict[str, Any] = Depends(get_current_user)):
    """List all API keys for the current user."""
    session = database.get_session()
    try:
        from core.db import APIKey as APIKeyModel

        keys = (
            session.query(APIKeyModel)
            .filter_by(user_id=user["id"])
            .order_by(APIKeyModel.created_at.desc())
            .all()
        )
        return APIKeyListResponse(items=[_to_response(k) for k in keys])
    finally:
        session.close()


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreate, user: dict[str, Any] = Depends(get_current_user)
):
    """Create a new API key for the current user."""
    full_key, prefix = generate_api_key()
    key_hash = hash_api_key(prefix, full_key.split(".", 1)[1])

    expires_at = None
    if body.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=body.expires_days)

    session = database.get_session()
    try:
        from core.db import APIKey as APIKeyModel

        api_key = APIKeyModel(
            user_id=user["id"],
            name=body.name,
            prefix=prefix,
            key_hash=key_hash,
            scopes=json.dumps(body.scopes),
            expires_at=expires_at,
        )
        session.add(api_key)
        session.commit()
        session.refresh(api_key)

        # Return full key only on creation
        response = _to_response(api_key)
        response.key = full_key
        return response
    finally:
        session.close()


@router.delete("/{key_id}", response_model=StatusResponse)
async def revoke_api_key(key_id: int, user: dict[str, Any] = Depends(get_current_user)):
    """Revoke (disable) an API key."""
    session = database.get_session()
    try:
        from core.db import APIKey as APIKeyModel

        api_key = (
            session.query(APIKeyModel).filter_by(id=key_id, user_id=user["id"]).first()
        )
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")

        api_key.is_active = False
        session.commit()
        return StatusResponse(status="ok", detail="API key revoked")
    finally:
        session.close()


def _to_response(api_key) -> APIKeyResponse:
    """Convert DB model to response schema."""
    import json

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=json.loads(api_key.scopes) if api_key.scopes else [],
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
        key=None,  # Never return full key in list/detail
    )
