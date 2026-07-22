"""
WebSocket endpoint for live vehicle sensor streaming.

Clients connect to::

    ws://host:8000/ws/vehicles/{vehicle_id}/live

and receive JSON-encoded sensor readings every 5 seconds.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import core.db as database
from core.config import SENSOR_COLUMNS
from core.logger import get_logger

log = get_logger("ws_live")

# Track active connections per vehicle for broadcasting
_active_connections: dict[int, set] = {}


async def vehicle_live_feed(websocket: Any, vehicle_id: int) -> None:
    """
    WebSocket handler for live vehicle sensor feed.

    Pushes the most recent sensor reading every 5 seconds.
    """
    await websocket.accept()
    log.info("WebSocket connected for vehicle %s", vehicle_id)

    # Register connection
    if vehicle_id not in _active_connections:
        _active_connections[vehicle_id] = set()
    _active_connections[vehicle_id].add(websocket)

    try:
        while True:
            reading = _get_latest_reading(vehicle_id)
            payload = {
                "vehicle_id": vehicle_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "reading": reading,
            }
            try:
                await websocket.send_json(payload)
            except Exception:
                break
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    finally:
        _active_connections.get(vehicle_id, set()).discard(websocket)
        log.info("WebSocket disconnected for vehicle %s", vehicle_id)


def _get_latest_reading(vehicle_id: int) -> dict[str, Any] | None:
    """Fetch the most recent sensor reading from the database."""
    session = database.get_session()
    try:
        reading = (
            session.query(database.SensorReading)
            .filter_by(
                vehicle_id=vehicle_id,
            )
            .order_by(database.SensorReading.timestamp.desc())
            .first()
        )

        if reading is None:
            return None

        return {
            col: getattr(reading, col, None)
            for col in SENSOR_COLUMNS + ["timestamp", "id"]
        }
    finally:
        session.close()


def broadcast_reading(vehicle_id: int, reading_data: dict) -> None:
    """Broadcast a new reading to all connected WebSocket clients for a vehicle."""
    connections = _active_connections.get(vehicle_id, set())
    if not connections:
        return
    payload = {
        "vehicle_id": vehicle_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "reading": reading_data,
    }
    for ws in connections.copy():
        try:
            # Use the running event loop to schedule the async send
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(ws.send_json(payload), loop)
                else:
                    loop.run_until_complete(ws.send_json(payload))
            except RuntimeError:
                pass
        except Exception:
            connections.discard(ws)
