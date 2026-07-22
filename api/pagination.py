"""
Cursor-based pagination for FastAPI with SQLAlchemy.

Provides a consistent pagination interface using opaque cursors
instead of offset/limit for better performance on large datasets.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


@dataclass
class PaginationParams:
    """Parsed pagination parameters from request."""

    cursor: str | None
    limit: int


def decode_cursor(cursor: str) -> dict[str, Any] | None:
    """Decode opaque cursor string to dict."""
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return None


def encode_cursor(data: dict[str, Any]) -> str:
    """Encode dict to opaque cursor string."""
    return base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":")).encode()
    ).decode()


class CursorPage(BaseModel, Generic[T]):
    """Cursor-based paginated response."""

    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    limit: int


def get_pagination_params(
    cursor: str | None = Query(None, description="Opaque cursor for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Max items per page"),
) -> PaginationParams:
    """FastAPI dependency to parse pagination parameters."""
    return PaginationParams(cursor=cursor, limit=limit)


async def paginate_query(
    query: Select,
    params: PaginationParams,
    session: AsyncSession,
    cursor_field: str = "id",
    descending: bool = True,
) -> tuple[list[Any], str | None, bool]:
    """
    Apply cursor-based pagination to a SQLAlchemy query.

    Args:
        query: SQLAlchemy Select query
        params: PaginationParams with cursor and limit
        session: AsyncSession for executing query
        cursor_field: Field name to use for cursor (must be unique and ordered)
        descending: Whether to order descending (newest first)

    Returns:
        Tuple of (items, next_cursor, has_more)
    """
    from sqlalchemy import desc

    model = query.column_descriptions[0]["type"]
    cursor_attr = getattr(model, cursor_field)

    # Apply cursor if provided
    if params.cursor:
        cursor_data = decode_cursor(params.cursor)
        if cursor_data:
            cursor_value = cursor_data.get(cursor_field)
            if cursor_value is not None:
                if descending:
                    query = query.where(cursor_attr < cursor_value)
                else:
                    query = query.where(cursor_attr > cursor_value)

    # Order and limit (+1 to detect has_more)
    if descending:
        query = query.order_by(desc(cursor_attr))
    else:
        query = query.order_by(cursor_attr)

    query = query.limit(params.limit + 1)

    result = await session.execute(query)
    items = result.scalars().all()

    has_more = len(items) > params.limit
    if has_more:
        items = items[: params.limit]

    next_cursor = None
    if items and has_more:
        last_item = items[-1]
        cursor_value = getattr(last_item, cursor_field)
        next_cursor = encode_cursor({cursor_field: cursor_value})

    return items, next_cursor, has_more
