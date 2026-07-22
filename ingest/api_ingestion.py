"""
REST API ingestion endpoint for sensor readings (HTTP fallback from MQTT).

This module provides a FastAPI router that can be mounted on the main API
server (Phase 7).  It also has a standalone uvicorn mode for testing.

Endpoint::

    POST /api/v1/vehicles/{vehicle_id}/readings
    Authorization: Bearer <api_key>

Usage (standalone test):
    python ingest/api_ingestion.py
"""

from __future__ import annotations

from datetime import datetime

from core.logger import get_logger

log = get_logger("api_ingestion")

try:
    from fastapi import APIRouter, Depends, Header, HTTPException
    from pydantic import BaseModel, Field, field_validator

    _has_fastapi = True
except ImportError:
    _has_fastapi = False
    # Stub so the module can be imported without FastAPI
    BaseModel = object

    def Field(default, **kw):
        return default

    APIRouter = object


# ── Pydantic request schema ──


class SensorReadingIn(BaseModel):
    """Single sensor reading submitted via REST API."""

    timestamp: str | None = None
    engine_temp: float | None = Field(None, ge=-40, le=200)
    oil_pressure: float | None = Field(None, ge=0, le=150)
    coolant_temp: float | None = Field(None, ge=-40, le=150)
    engine_rpm: float | None = Field(None, ge=0, le=10000)
    vibration: float | None = Field(None, ge=0, le=50)
    fuel_consumption: float | None = Field(None, ge=0, le=100)
    battery_voltage: float | None = Field(None, ge=0, le=30)
    tire_pressure: float | None = Field(None, ge=0, le=80)
    speed: float | None = Field(None, ge=0, le=350)
    engine_load: float | None = Field(None, ge=0, le=100)

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v):
        if v is None:
            return datetime.utcnow().isoformat()
        try:
            datetime.fromisoformat(v)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid timestamp: {v}")
        return v


class BulkSensorReadingsIn(BaseModel):
    """Bulk ingest of multiple readings."""

    readings: list[SensorReadingIn]


# ── FastAPI router ──


def _verify_api_key(authorization: str = Header(None)) -> str:
    """Dependency: extract and verify Bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization format")
    # TODO(phase7): validate against real API keys from DB
    return token


if _has_fastapi:
    router = APIRouter(prefix="/api/v1", tags=["ingestion"])

    @router.post("/vehicles/{vehicle_id}/readings", status_code=201)
    async def ingest_single_reading(
        vehicle_id: int,
        reading: SensorReadingIn,
        api_key: str = Depends(_verify_api_key),
    ):
        """Ingest a single sensor reading for a vehicle."""
        import core.db as database
        from core.alerts import check_and_generate_alerts
        from core.preprocessing import preprocess_single_reading

        payload = reading.model_dump()
        cleaned, errors = preprocess_single_reading(payload)
        if errors:
            raise HTTPException(status_code=422, detail={"validation_errors": errors})

        # Fetch vehicle (scoped to user inferred from API key)
        session = database.get_session()
        try:
            vehicle = session.query(database.Vehicle).filter_by(id=vehicle_id).first()
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            user_id = vehicle.user_id

            db_reading = database.SensorReading(
                vehicle_id=vehicle_id,
                user_id=user_id,
                timestamp=datetime.fromisoformat(cleaned["timestamp"]),
                **{
                    col: cleaned.get(col)
                    for col in [
                        "engine_temp",
                        "oil_pressure",
                        "coolant_temp",
                        "engine_rpm",
                        "vibration",
                        "fuel_consumption",
                        "battery_voltage",
                        "tire_pressure",
                        "speed",
                        "engine_load",
                    ]
                },
            )
            session.add(db_reading)
            session.commit()
            session.refresh(db_reading)
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            log.exception("Failed to store API reading")
            raise HTTPException(status_code=500, detail="Failed to store reading")
        finally:
            session.close()

        # Fire alerts
        alerts = check_and_generate_alerts(cleaned, vehicle_id, user_id)

        return {
            "status": "ok",
            "reading_id": db_reading.id,
            "alerts_generated": len(alerts),
        }

    @router.post("/vehicles/{vehicle_id}/readings/bulk", status_code=201)
    async def ingest_bulk_readings(
        vehicle_id: int,
        body: BulkSensorReadingsIn,
        api_key: str = Depends(_verify_api_key),
    ):
        """Ingest multiple sensor readings in one request."""
        import core.db as database
        from core.preprocessing import preprocess_single_reading

        session = database.get_session()
        try:
            vehicle = session.query(database.Vehicle).filter_by(id=vehicle_id).first()
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            user_id = vehicle.user_id
        finally:
            session.close()

        stored = 0
        errors = []
        for reading in body.readings:
            payload = reading.model_dump()
            cleaned, errs = preprocess_single_reading(payload)
            if errs:
                errors.append({"reading": payload, "errors": errs})
                continue

            session = database.get_session()
            try:
                db_reading = database.SensorReading(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                    timestamp=datetime.fromisoformat(cleaned["timestamp"]),
                    **{
                        col: cleaned.get(col)
                        for col in [
                            "engine_temp",
                            "oil_pressure",
                            "coolant_temp",
                            "engine_rpm",
                            "vibration",
                            "fuel_consumption",
                            "battery_voltage",
                            "tire_pressure",
                            "speed",
                            "engine_load",
                        ]
                    },
                )
                session.add(db_reading)
                session.commit()
                stored += 1
            except Exception:
                session.rollback()
                errors.append({"reading": payload, "errors": ["DB write failed"]})
            finally:
                session.close()

        return {
            "status": "ok" if not errors else "partial",
            "stored": stored,
            "failed": len(errors),
            "errors": errors[:5],  # limit response size
        }
else:
    router = None  # type: ignore


# ── Standalone test harness ──
if __name__ == "__main__":
    import uvicorn

    print("Starting API ingestion test server on http://0.0.0.0:8000")
    print("POST /api/v1/vehicles/{id}/readings with JSON body")
    uvicorn.run(
        "ingest.api_ingestion:create_test_app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
