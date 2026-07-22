"""
Async proxy for synchronous ``db`` functions.

Each function wraps the corresponding ``db.*`` call with
``sync_to_async`` so it runs in a thread executor and does
not block the FastAPI event loop.

Usage inside an ``async def`` endpoint::

    from api.db_proxy import async_get_vehicles_for_user

    vehicles = await async_get_vehicles_for_user(user["id"])
"""

from __future__ import annotations

from typing import Any

import core.db as database
from api.dependencies import sync_to_async

# ── Vehicles ──


async def async_get_vehicles_for_user(user_id: int) -> list[Any]:
    return await sync_to_async(database.get_vehicles_for_user, user_id)


async def async_get_vehicle_by_id(vehicle_id: int, user_id: int) -> Any | None:
    return await sync_to_async(database.get_vehicle_by_id, vehicle_id, user_id)


# ── Sensor readings ──


async def async_get_sensor_readings(vehicle_id: int, user_id: int, **kwargs) -> Any:
    return await sync_to_async(
        lambda: database.get_sensor_readings(vehicle_id, user_id, **kwargs)
    )


# ── Predictions ──


async def async_get_latest_prediction(vehicle_id: int, user_id: int) -> Any | None:
    return await sync_to_async(database.get_latest_prediction, vehicle_id, user_id)


async def async_get_predictions_for_vehicle(vehicle_id: int, user_id: int) -> list[Any]:
    return await sync_to_async(
        database.get_predictions_for_vehicle, vehicle_id, user_id
    )


async def async_get_latest_predictions_for_user(user_id: int) -> dict[int, Any]:
    return await sync_to_async(database.get_latest_predictions_for_user, user_id)


async def async_save_prediction(**kwargs) -> Any:
    return await sync_to_async(lambda: database.save_prediction(**kwargs))


# ── Alerts ──


async def async_get_active_alerts(
    user_id: int, vehicle_id: int | None = None
) -> list[Any]:
    return await sync_to_async(database.get_active_alerts, user_id, vehicle_id)


async def async_get_all_alerts(
    user_id: int, vehicle_id: int | None = None
) -> list[Any]:
    return await sync_to_async(database.get_all_alerts, user_id, vehicle_id)


async def async_dismiss_alert(alert_id: int, user_id: int) -> bool:
    return await sync_to_async(database.dismiss_alert, alert_id, user_id)


async def async_acknowledge_alert(
    alert_id: int, user_id: int, acknowledged_by: int
) -> bool:
    return await sync_to_async(
        database.acknowledge_alert, alert_id, user_id, acknowledged_by
    )


# ── Models ──


async def async_get_best_model(
    user_id: int, vehicle_id: int | None = None
) -> Any | None:
    return await sync_to_async(database.get_best_model, user_id, vehicle_id)


async def async_get_all_trained_models(user_id: int) -> list[Any]:
    return await sync_to_async(database.get_all_trained_models, user_id)


# ── Maintenance ──


async def async_get_maintenance_history(vehicle_id: int, user_id: int) -> list[Any]:
    return await sync_to_async(database.get_maintenance_history, vehicle_id, user_id)


async def async_create_maintenance_record(**kwargs) -> Any:
    return await sync_to_async(lambda: database.create_maintenance_record(**kwargs))


async def async_update_maintenance_record(
    record_id: int, user_id: int, **kwargs
) -> bool:
    return await sync_to_async(
        lambda: database.update_maintenance_record(record_id, user_id, **kwargs)
    )


async def async_delete_maintenance_record(record_id: int, user_id: int) -> bool:
    return await sync_to_async(database.delete_maintenance_record, record_id, user_id)


# ── Auth / Users ──


async def async_authenticate_user(username: str, password: str) -> Any | None:
    return await sync_to_async(database.authenticate_user, username, password)


async def async_create_user(**kwargs) -> Any | None:
    return await sync_to_async(lambda: database.create_user(**kwargs))
