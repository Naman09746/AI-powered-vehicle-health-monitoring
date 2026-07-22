"""
Pydantic v2 schemas for request validation and response serialization.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ═══════════════════════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════════════════════


class LoginRequest(BaseModel):
    username: str
    password: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"username": "jdoe", "password": "securePassword123"},
            ]
        }
    }


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    role: str
    name: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "token": "eyJhbGciOiJIUzI1NiIs...",
                    "user_id": 1,
                    "username": "jdoe",
                    "role": "fleet_manager",
                    "name": "John Doe",
                }
            ]
        }
    }


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    name: str | None = None
    email: str | None = None
    phone: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "jdoe",
                    "password": "securePassword123",
                    "name": "John Doe",
                    "email": "jdoe@example.com",
                    "phone": "+1-555-123-4567",
                }
            ]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Vehicle
# ═══════════════════════════════════════════════════════════════════════════════


class VehicleCreate(BaseModel):
    vehicle_id_display: str
    model: str | None = None
    manufacturing_year: int | None = Field(None, ge=1990, le=2030)
    engine_type: str | None = None
    mileage: float | None = Field(None, ge=0)
    last_service_date: date | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "vehicle_id_display": "TRUCK-001",
                    "model": "Volvo FH16",
                    "manufacturing_year": 2022,
                    "engine_type": "Diesel",
                    "mileage": 45230.5,
                    "last_service_date": "2026-03-15",
                }
            ]
        }
    }


class VehicleResponse(BaseModel):
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "vehicle_id_display": "TRUCK-001",
                    "model": "Volvo FH16",
                    "manufacturing_year": 2022,
                    "engine_type": "Diesel",
                    "mileage": 45230.5,
                    "last_service_date": "2026-03-15",
                    "created_at": "2026-01-10T08:30:00Z",
                }
            ]
        },
    }

    id: int
    vehicle_id_display: str
    model: str | None = None
    manufacturing_year: int | None = None
    engine_type: str | None = None
    mileage: float | None = None
    last_service_date: date | None = None
    created_at: datetime | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Sensor Readings
# ═══════════════════════════════════════════════════════════════════════════════


class SensorReadingIn(BaseModel):
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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp": "2026-07-14T10:30:00Z",
                    "engine_temp": 92.5,
                    "oil_pressure": 45.2,
                    "coolant_temp": 88.1,
                    "engine_rpm": 2200.0,
                    "vibration": 1.2,
                    "fuel_consumption": 8.7,
                    "battery_voltage": 13.4,
                    "tire_pressure": 32.0,
                    "speed": 65.0,
                    "engine_load": 55.0,
                }
            ]
        }
    }

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: Any) -> str:
        if v is None:
            return datetime.utcnow().isoformat()
        try:
            datetime.fromisoformat(str(v))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid timestamp: {v}")
        return str(v)


class SensorReadingResponse(BaseModel):
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 101,
                    "timestamp": "2026-07-14T10:30:00Z",
                    "engine_temp": 92.5,
                    "oil_pressure": 45.2,
                    "coolant_temp": 88.1,
                    "engine_rpm": 2200.0,
                    "vibration": 1.2,
                    "fuel_consumption": 8.7,
                    "battery_voltage": 13.4,
                    "tire_pressure": 32.0,
                    "speed": 65.0,
                    "engine_load": 55.0,
                }
            ]
        },
    }

    id: int
    timestamp: datetime | None = None
    engine_temp: float | None = None
    oil_pressure: float | None = None
    coolant_temp: float | None = None
    engine_rpm: float | None = None
    vibration: float | None = None
    fuel_consumption: float | None = None
    battery_voltage: float | None = None
    tire_pressure: float | None = None
    speed: float | None = None
    engine_load: float | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Predictions
# ═══════════════════════════════════════════════════════════════════════════════


class PredictionResponse(BaseModel):
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 42,
                    "prediction": "maintenance",
                    "failure_prob": 0.65,
                    "health_score": 72.3,
                    "predicted_at": "2026-07-14T10:30:00Z",
                }
            ]
        },
    }

    id: int
    prediction: str | None = None
    failure_prob: float | None = None
    health_score: float | None = None
    predicted_at: datetime | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Alerts
# ═══════════════════════════════════════════════════════════════════════════════


class AlertResponse(BaseModel):
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "alert_type": "high_engine_temp",
                    "severity": "High",
                    "message": "Engine temperature is critically high (118.5 deg C)!",
                    "is_dismissed": False,
                    "created_at": "2026-07-14T10:30:00Z",
                }
            ]
        },
    }

    id: int
    alert_type: str
    severity: str
    message: str
    is_dismissed: bool = False
    created_at: datetime | None = None


class AlertAcknowledge(BaseModel):
    acknowledged_by: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"acknowledged_by": 2},
            ]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Generic
# ═══════════════════════════════════════════════════════════════════════════════


class StatusResponse(BaseModel):
    status: str = "ok"
    detail: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"status": "ok", "detail": "User 'jdoe' created"},
            ]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Token Refresh / Revocation
# ═══════════════════════════════════════════════════════════════════════════════


class RefreshTokenResponse(BaseModel):
    token: str
    user_id: int
    username: str
    role: str
    name: str | None = None
    refresh_count: int = 0
    max_refresh_count: int = 10

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "token": "new-rotated-token-value...",
                    "user_id": 1,
                    "username": "jdoe",
                    "role": "fleet_manager",
                    "name": "John Doe",
                    "refresh_count": 1,
                    "max_refresh_count": 10,
                }
            ]
        }
    }


class RevokeTokenRequest(BaseModel):
    reason: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"reason": "User-initiated logout from all devices"},
            ]
        }
    }


class RevokeTokenResponse(BaseModel):
    status: str = "ok"
    detail: str | None = None
    revoked_sessions_count: int = 0
