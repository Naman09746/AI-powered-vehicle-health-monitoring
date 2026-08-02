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

from datetime import datetime
import json
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

def start_fleet_simulation():
    """Auto-start simulation for all vehicles in the database."""
    session = database.get_session()
    try:
        vehicles = session.query(database.Vehicle).all()
        count = 0
        for v in vehicles:
            with _simulation_lock:
                if v.id not in _simulations or not _simulations[v.id].get("running"):
                    _simulations[v.id] = {
                        "running": True,
                        "profile": "healthy",
                        "interval": 5.0,
                        "tick": 0,
                        "last_reading": None,
                    }
                    thread = threading.Thread(
                        target=_simulation_worker,
                        args=(v.id, "healthy", 5.0, v.user_id, v.vehicle_id_display),
                        daemon=True,
                    )
                    thread.start()
                    count += 1
        if count > 0:
            log.info("Auto-started fleet simulation for %d vehicles", count)
    except Exception as e:
        log.error("Failed to auto-start fleet simulation: %s", e)
    finally:
        session.close()


def ensure_vehicle_simulation(vehicle_id: int, user_id: int, vehicle_id_display: str, interval: float = 2.0):
    """Ensure a simulation thread is actively running for this vehicle and seed initial readings if empty."""
    session = database.get_session()
    try:
        readings_count = session.query(database.SensorReading).filter_by(vehicle_id=vehicle_id).count()
        if readings_count == 0:
            upload_id = database.get_or_create_default_upload(vehicle_id, user_id)
            now = time.time()
            for i in range(50):
                tick = i
                reading = generate_realistic_row(vehicle_profile="healthy", tick=tick, seed=tick)
                db_reading = database.SensorReading(
                    upload_id=upload_id,
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                    timestamp=datetime.fromtimestamp(now - (50 - i) * 5),
                    dtc_codes=json.dumps(reading.get("dtc_codes", [])),
                    **{col: reading.get(col) for col in SENSOR_COLUMNS if col in reading},
                )
                session.add(db_reading)
            session.commit()
            log.info("Seeded 50 initial readings for vehicle %s", vehicle_id_display)
    except Exception as e:
        session.rollback()
        log.error("Failed to seed initial readings for vehicle %s: %s", vehicle_id_display, e)
    finally:
        session.close()

    with _simulation_lock:
        if vehicle_id not in _simulations or not _simulations[vehicle_id].get("running"):
            _simulations[vehicle_id] = {
                "running": True,
                "profile": "healthy",
                "interval": interval,
                "tick": 0,
                "last_reading": None,
            }
            thread = threading.Thread(
                target=_simulation_worker,
                args=(vehicle_id, "healthy", interval, user_id, vehicle_id_display),
                daemon=True,
            )
            thread.start()
            log.info("Auto-started high-speed simulation (%.1fs) for vehicle %s", interval, vehicle_id_display)


def seed_demo_fleet_for_user(user_id: int):
    """Pre-populates a rich demo fleet with historical telemetry data for zero-wait evaluations."""
    session = database.get_session()
    try:
        existing = session.query(database.Vehicle).filter_by(user_id=user_id).first()
        if not existing:
            v1 = database.create_vehicle(
                user_id=user_id,
                vehicle_id_display="VH-DEMO-001",
                model="Toyota Camry Hybrid",
                manufacturing_year=2024,
                engine_type="Hybrid",
                mileage=12500,
            )
            v2 = database.create_vehicle(
                user_id=user_id,
                vehicle_id_display="VH-DEMO-002",
                model="Tesla Model 3",
                manufacturing_year=2023,
                engine_type="Electric",
                mileage=24100,
            )
            for v in [v1, v2]:
                if v:
                    ensure_vehicle_simulation(v.id, user_id, v.vehicle_id_display)
    except Exception as e:
        log.error("Failed to seed demo fleet for user %s: %s", user_id, e)
    finally:
        session.close()




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
                timestamp=datetime.utcnow(),
                dtc_codes=json.dumps(reading.get("dtc_codes", [])),
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


from fastapi import APIRouter, Depends, HTTPException, Request
from api.limiter import limiter


@router.post("/start/{vehicle_id}")
@limiter.limit("5/minute")
async def start_simulation(
    request: Request,
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


from fastapi import WebSocket

@router.websocket("/stream/{vehicle_id}")
async def simulator_websocket(websocket: WebSocket, vehicle_id: int):
    """WebSocket stream endpoint for live vehicle simulator telemetry."""
    from api.websocket import vehicle_live_feed
    await vehicle_live_feed(websocket, vehicle_id)

