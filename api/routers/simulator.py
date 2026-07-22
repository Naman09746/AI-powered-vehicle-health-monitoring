"""
Simulator router — start/stop live data simulation for a vehicle.
Directly generates realistic sensor readings and saves to DB
without requiring MQTT infrastructure.

Endpoints:
  POST /api/v1/simulator/start/{vehicle_id} - start simulation
  POST /api/v1/simulator/stop/{vehicle_id}  - stop simulation
  GET  /api/v1/simulator/status/{vehicle_id} - check if running
"""

from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

import core.db as database
from core.alerts import check_and_generate_alerts
from api.dependencies import get_current_user
from api.websocket import broadcast_reading
from core.config import SENSOR_COLUMNS
from scripts.generate_data import generate_realistic_row
from core.logger import get_logger

log = get_logger("api.simulator")
router = APIRouter(prefix="/api/v1/simulator", tags=["simulator"])

# Track active simulation threads per vehicle
_simulations: dict[int, dict] = {}
_simulation_lock = threading.Lock()


def _simulation_worker(
    vehicle_id: int,
    profile: str,
    interval: float,
    user_id: int,
    vehicle_id_display: str,
):
    """Background thread that generates readings and saves to DB."""
    tick = 0
    log.info(
        "Simulation started for vehicle %s (profile=%s, interval=%.1fs)",
        vehicle_id_display,
        profile,
        interval,
    )

    try:
        while True:
            with _simulation_lock:
                if not _simulations.get(vehicle_id, {}).get("running", False):
                    log.info("Simulation stopped for vehicle %s", vehicle_id_display)
                    break

            # Generate a realistic reading
            reading = generate_realistic_row(
                vehicle_profile=profile, tick=tick, seed=tick
            )
            reading["vehicle_id_display"] = vehicle_id_display
            reading["profile"] = profile

            # Save to database
            upload_id = database.get_or_create_default_upload(vehicle_id, user_id)

            db_reading = database.SensorReading(
                upload_id=upload_id,
                vehicle_id=vehicle_id,
                user_id=user_id,
                timestamp=time.time(),
                **{col: reading.get(col) for col in SENSOR_COLUMNS if col in reading},
            )

            session = database.get_session()
            try:
                session.add(db_reading)
                session.commit()
            except Exception as e:
                session.rollback()
                log.error("Failed to save reading: %s", e)
                session.close()
                continue
            finally:
                session.close()

            # Check for alerts
            alerts = check_and_generate_alerts(
                reading, vehicle_id, user_id, failure_prob=None
            )
            if alerts:
                log.info(
                    "Generated %d alert(s) for %s", len(alerts), vehicle_id_display
                )

            # Broadcast to WebSocket clients
            broadcast_reading(vehicle_id, reading)

            tick += 1

            # Update status
            with _simulation_lock:
                if vehicle_id in _simulations:
                    _simulations[vehicle_id]["tick"] = tick
                    _simulations[vehicle_id]["last_reading"] = reading

            time.sleep(interval)

    except Exception as e:
        log.error("Simulation error for %s: %s", vehicle_id_display, e)
    finally:
        with _simulation_lock:
            if vehicle_id in _simulations:
                _simulations[vehicle_id]["running"] = False


@router.post("/start/{vehicle_id}")
async def start_simulation(
    vehicle_id: int,
    profile: str = "healthy",
    interval: float = 3.0,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Start live data simulation for a vehicle."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    with _simulation_lock:
        if vehicle_id in _simulations and _simulations[vehicle_id].get("running"):
            return JSONResponse(
                status_code=200,
                content={
                    "status": "already_running",
                    "profile": _simulations[vehicle_id].get("profile"),
                },
            )

        if profile not in ("healthy", "degrading", "critical", "intermittent_fault"):
            raise HTTPException(status_code=400, detail=f"Invalid profile: {profile}")

        _simulations[vehicle_id] = {
            "running": True,
            "profile": profile,
            "interval": interval,
            "tick": 0,
            "last_reading": None,
        }

    thread = threading.Thread(
        target=_simulation_worker,
        args=(vehicle_id, profile, interval, user["id"], vehicle.vehicle_id_display),
        daemon=True,
    )
    thread.start()

    return {
        "status": "started",
        "vehicle_id": vehicle_id,
        "profile": profile,
        "interval": interval,
    }


@router.post("/stop/{vehicle_id}")
async def stop_simulation(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Stop live data simulation."""
    with _simulation_lock:
        if vehicle_id not in _simulations or not _simulations[vehicle_id].get(
            "running"
        ):
            return JSONResponse(
                status_code=200,
                content={"status": "not_running"},
            )
        _simulations[vehicle_id]["running"] = False
        info = dict(_simulations[vehicle_id])

    return {
        "status": "stopped",
        "vehicle_id": vehicle_id,
        "ticks_generated": info.get("tick", 0),
    }


@router.get("/status/{vehicle_id}")
async def simulation_status(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Check if simulation is running for a vehicle."""
    with _simulation_lock:
        if vehicle_id in _simulations and _simulations[vehicle_id].get("running"):
            info = dict(_simulations[vehicle_id])
            return {
                "running": True,
                "profile": info.get("profile"),
                "interval": info.get("interval"),
                "tick": info.get("tick", 0),
                "last_reading": info.get("last_reading"),
            }
    return {"running": False}
