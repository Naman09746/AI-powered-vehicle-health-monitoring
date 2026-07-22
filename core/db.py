"""
Database models and CRUD helpers using SQLAlchemy.
Supports both SQLite (dev) and PostgreSQL (prod).
All queries are scoped by user_id for data isolation.
"""

import datetime
import hashlib
import json
import time
from collections.abc import Generator
from contextlib import contextmanager
from functools import wraps
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from core.config import DATABASE_URL

# ──────────────────────────────────────────────
# Simple TTL cache for read-only queries
# ──────────────────────────────────────────────

_cached_results: dict[str, tuple[float, Any]] = {}
_cache_ttl_seconds = 10  # Short TTL — data refreshes on next page interaction


def cached(ttl: int = 10):
    """Decorator that caches the return value of a read-only function for *ttl* seconds."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{hash(args)}:{hash(frozenset(kwargs.items()))}"
            now = time.monotonic()
            if key in _cached_results:
                timestamp, value = _cached_results[key]
                if now - timestamp < ttl:
                    return value
            result = func(*args, **kwargs)
            _cached_results[key] = (now, result)
            return result

        return wrapper

    return decorator


Base = declarative_base()

# ──────────────────────────────────────────────
# Engine setup — SQLite (dev) or PostgreSQL (prod)
# ──────────────────────────────────────────────
# Normalise URL: db.py uses SYNC sessions, so replace asyncpg (async-only)
# with psycopg2 (sync driver) when connecting to PostgreSQL.
_sync_url = DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
).replace("sqlite+aiosqlite://", "sqlite://")

if _sync_url.startswith("postgresql://") and "+psycopg2" not in _sync_url:
    _sync_url = _sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

if "postgresql" in _sync_url and "sslmode" not in _sync_url and "localhost" not in _sync_url and "127.0.0.1" not in _sync_url:
    sep = "&" if "?" in _sync_url else "?"
    _sync_url += f"{sep}sslmode=require"

_is_sqlite = _sync_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        _sync_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        _sync_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_db() -> Generator:
    """
    Context manager for safe database sessions.
    Automatically commits on success, rolls back on error.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ──────────────────────────────────────────────
# ORM Models
# ──────────────────────────────────────────────


class Organization(Base):
    """Multi-tenant organization that owns vehicles and users."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    plan = Column(String, default="free")  # free | pro | enterprise
    max_vehicles = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    role = Column(
        String, default="owner"
    )  # admin | fleet_manager | technician | driver
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    vehicles = relationship(
        "Vehicle", back_populates="user", cascade="all, delete-orphan"
    )
    organization = relationship("Organization", back_populates="users")


class Session(Base):
    """User session tokens for auth (replaces bare st.session_state)."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    jti = Column(String, nullable=True, unique=True)  # JWT ID for blocklist tracking
    ip_address = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    refresh_count = Column(Integer, default=0)  # Track rotation count
    is_revoked = Column(Boolean, default=False)  # Hard revocation flag
    revoked_at = Column(DateTime, nullable=True)  # When revocation occurred
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class APIKey(Base):
    """API keys for machine-to-machine authentication."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)  # Human-readable name
    prefix = Column(
        String, nullable=False
    )  # Short prefix for display (e.g., "vhm_abc123")
    key_hash = Column(String, nullable=False, unique=True)  # SHA256 of prefix.key
    scopes = Column(Text, default="[]")  # JSON array of scopes
    expires_at = Column(DateTime, nullable=True)  # Optional expiry
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)


class WebhookSubscription(Base):
    """Webhook subscription for async event delivery."""

    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=True)
    events = Column(
        Text, nullable=False, default='["*"]'
    )  # JSON array of events or "*" for all
    is_active = Column(Boolean, default=True)
    retry_count = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=10)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    __table_args__ = (Index("ix_webhook_subscriptions_user", "user_id", "is_active"),)


class WebhookLog(Base):
    """Delivery log for webhook events."""

    __tablename__ = "webhook_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_id = Column(Integer, ForeignKey("webhook_subscriptions.id"), nullable=False)
    event = Column(String, nullable=False)
    status = Column(String, nullable=False)  # pending, delivered, failed
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    attempt = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (Index("ix_webhook_logs_webhook", "webhook_id", "created_at"),)


class AuditLog(Base):
    """Audit trail for critical actions (model promotions, deletions, etc.)."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # e.g. "model_promoted", "vehicle_deleted"
    resource_type = Column(String, nullable=True)  # e.g. "TrainedModel", "Vehicle"
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)  # JSON with extra context
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id_display = Column(String, nullable=False)
    model = Column(String)
    manufacturing_year = Column(Integer)
    engine_type = Column(String)
    mileage = Column(Float)
    last_service_date = Column(Date)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="vehicles")
    uploads = relationship(
        "SensorUpload", back_populates="vehicle", cascade="all, delete-orphan"
    )
    readings = relationship(
        "SensorReading", back_populates="vehicle", cascade="all, delete-orphan"
    )
    maintenance_records = relationship(
        "MaintenanceHistory", back_populates="vehicle", cascade="all, delete-orphan"
    )
    alerts = relationship(
        "Alert", back_populates="vehicle", cascade="all, delete-orphan"
    )
    predictions = relationship(
        "Prediction", back_populates="vehicle", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("user_id", "vehicle_id_display"),)


class SensorUpload(Base):
    __tablename__ = "sensor_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String)
    row_count_raw = Column(Integer)
    row_count_clean = Column(Integer)
    upload_time = Column(DateTime, default=datetime.datetime.utcnow)
    preprocessing_log = Column(Text)  # JSON string

    vehicle = relationship("Vehicle", back_populates="uploads")
    readings = relationship(
        "SensorReading", back_populates="upload", cascade="all, delete-orphan"
    )


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(Integer, ForeignKey("sensor_uploads.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime)
    engine_temp = Column(Float)
    oil_pressure = Column(Float)
    coolant_temp = Column(Float)
    engine_rpm = Column(Float)
    vibration = Column(Float)
    fuel_consumption = Column(Float)
    battery_voltage = Column(Float)
    tire_pressure = Column(Float)
    speed = Column(Float)
    engine_load = Column(Float)
    failure_label = Column(Integer)  # 0 or 1

    upload = relationship("SensorUpload", back_populates="readings")
    vehicle = relationship("Vehicle", back_populates="readings")

    __table_args__ = (
        Index("ix_sensor_readings_vehicle_timestamp", "vehicle_id", "timestamp"),
    )


class TrainedModel(Base):
    __tablename__ = "trained_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, nullable=True)
    model_name = Column(String, nullable=False)
    model_path = Column(String, nullable=False)
    scaler_path = Column(String)

    # Metrics
    accuracy = Column(Float)
    precision_score = Column(Float)
    recall = Column(Float)
    f1 = Column(Float)
    roc_auc = Column(Float)

    # Champion / Challenger tracking
    is_best = Column(Boolean, default=False)
    is_champion = Column(Boolean, default=False)
    model_version = Column(String, nullable=True)  # semver e.g. "1.2.0"
    challenger_vs_champion_delta = Column(
        Float, nullable=True
    )  # F1/ROC-AUC improvement

    # Reproducibility
    training_data_hash = Column(String, nullable=True)  # md5 of training data
    feature_columns_json = Column(Text, nullable=True)  # JSON list of feature cols

    trained_at = Column(DateTime, default=datetime.datetime.utcnow)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    model_id = Column(Integer, ForeignKey("trained_models.id"), nullable=True)
    prediction = Column(String)
    failure_prob = Column(Float)
    health_score = Column(Float)
    top_features = Column(Text)  # JSON
    predicted_at = Column(DateTime, default=datetime.datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="predictions")


class MaintenanceHistory(Base):
    __tablename__ = "maintenance_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    service_date = Column(Date, nullable=False)
    service_type = Column(String, nullable=False)
    parts_replaced = Column(String)
    cost = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="maintenance_records")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    alert_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(String, nullable=False)
    is_dismissed = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    alert_fingerprint = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="alerts")

    __table_args__ = (Index("ix_alerts_user_dismissed", "user_id", "is_dismissed"),)


class Incident(Base):
    """A critical incident ticket — created when multiple High alerts
    fire for the same vehicle within a short window."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    severity = Column(String, default="High")
    status = Column(String, default="open")  # open | investigating | resolved
    related_alert_ids = Column(Text)  # JSON list of alert IDs
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class PushSubscription(Base):
    """Browser Web Push subscription for real-time alert delivery."""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class NotificationPreferences(Base):
    """Per-user notification channel preferences."""

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    email_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=False)
    sms_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String, nullable=True)  # e.g. "22:00"
    quiet_hours_end = Column(String, nullable=True)  # e.g. "07:00"
    min_severity = Column(String, default="Medium")  # only alert above this
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


# ──────────────────────────────────────────────
# Database initialization
# ──────────────────────────────────────────────


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session():
    """Get a new database session (legacy — prefer `with get_db():` for new code)."""
    return SessionLocal()


# ──────────────────────────────────────────────
# User CRUD
# ──────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    import bcrypt

    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_user(
    username: str,
    password: str,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> User | None:
    """Create a new user. Returns None if username already exists."""
    session = get_session()
    try:
        existing = session.query(User).filter_by(username=username).first()
        if existing:
            return None
        user = User(
            username=username,
            password_hash=hash_password(password),
            name=name,
            email=email,
            phone=phone,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def authenticate_user(username: str, password: str) -> User | None:
    """Authenticate user by username and password. Returns User or None."""
    session = get_session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if user and verify_password(password, user.password_hash):
            return user
        return None
    finally:
        session.close()


def get_user_by_id(user_id: int) -> User | None:
    """Get user by ID."""
    session = get_session()
    try:
        return session.query(User).filter_by(id=user_id).first()
    finally:
        session.close()


# ──────────────────────────────────────────────
# Vehicle CRUD
# ──────────────────────────────────────────────


def create_vehicle(
    user_id: int,
    vehicle_id_display: str,
    model: str | None = None,
    manufacturing_year: int | None = None,
    engine_type: str | None = None,
    mileage: float | None = None,
    last_service_date=None,
) -> Vehicle | None:
    """Create a vehicle for a user. Returns None if vehicle_id_display already exists for that user."""
    session = get_session()
    try:
        existing = (
            session.query(Vehicle)
            .filter_by(user_id=user_id, vehicle_id_display=vehicle_id_display)
            .first()
        )
        if existing:
            return None
        vehicle = Vehicle(
            user_id=user_id,
            vehicle_id_display=vehicle_id_display,
            model=model,
            manufacturing_year=manufacturing_year,
            engine_type=engine_type,
            mileage=mileage,
            last_service_date=last_service_date,
        )
        session.add(vehicle)
        session.commit()
        session.refresh(vehicle)
        return vehicle
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@cached(ttl=10)
def get_vehicles_for_user(user_id: int) -> list[Vehicle]:
    """Get all vehicles for a user."""
    session = get_session()
    try:
        return (
            session.query(Vehicle)
            .filter_by(user_id=user_id)
            .order_by(Vehicle.created_at.desc())
            .all()
        )
    finally:
        session.close()


def get_vehicle_by_id(vehicle_id: int, user_id: int) -> Vehicle | None:
    """Get a specific vehicle, scoped by user."""
    session = get_session()
    try:
        return session.query(Vehicle).filter_by(id=vehicle_id, user_id=user_id).first()
    finally:
        session.close()


def delete_vehicle(vehicle_id: int, user_id: int) -> bool:
    """Delete a vehicle and all its cascaded data. Returns True if deleted."""
    session = get_session()
    try:
        vehicle = (
            session.query(Vehicle).filter_by(id=vehicle_id, user_id=user_id).first()
        )
        if not vehicle:
            return False
        session.delete(vehicle)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ──────────────────────────────────────────────
# Sensor Upload CRUD
# ──────────────────────────────────────────────


def create_sensor_upload(
    vehicle_id: int,
    user_id: int,
    filename: str,
    row_count_raw: int,
    row_count_clean: int,
    preprocessing_log: str,
) -> SensorUpload:
    """Create a sensor upload record."""
    session = get_session()
    try:
        upload = SensorUpload(
            vehicle_id=vehicle_id,
            user_id=user_id,
            filename=filename,
            row_count_raw=row_count_raw,
            row_count_clean=row_count_clean,
            preprocessing_log=preprocessing_log,
        )
        session.add(upload)
        session.commit()
        session.refresh(upload)
        return upload
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_sensor_upload(upload_id: int, user_id: int) -> bool:
    """Delete a sensor upload record and cascade delete readings."""
    session = get_session()
    try:
        upload = (
            session.query(SensorUpload)
            .filter(SensorUpload.id == upload_id, SensorUpload.user_id == user_id)
            .first()
        )
        if not upload:
            return False
        session.delete(upload)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_trained_model(model_id: int, user_id: int) -> bool:
    """Delete a trained model record."""
    import os
    session = get_session()
    try:
        model = (
            session.query(TrainedModel)
            .filter(TrainedModel.id == model_id, TrainedModel.user_id == user_id)
            .first()
        )
        if not model:
            return False
        if model.model_path and os.path.exists(model.model_path):
            try:
                os.remove(model.model_path)
            except Exception:
                pass
        if model.scaler_path and os.path.exists(model.scaler_path):
            try:
                os.remove(model.scaler_path)
            except Exception:
                pass
        # Nullify model references in predictions before deleting
        session.query(Prediction).filter(Prediction.model_id == model_id).update({Prediction.model_id: None})
        session.delete(model)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()



def save_sensor_readings(upload_id: int, vehicle_id: int, user_id: int, df) -> int:
    """Bulk-insert sensor readings from a DataFrame. Returns number of rows inserted."""
    import pandas as pd

    session = get_session()
    try:
        records = []
        for _, row in df.iterrows():
            reading = SensorReading(
                upload_id=upload_id,
                vehicle_id=vehicle_id,
                user_id=user_id,
                timestamp=pd.to_datetime(row.get("timestamp"))
                if pd.notna(row.get("timestamp"))
                else None,
                engine_temp=row.get("engine_temp"),
                oil_pressure=row.get("oil_pressure"),
                coolant_temp=row.get("coolant_temp"),
                engine_rpm=row.get("engine_rpm"),
                vibration=row.get("vibration"),
                fuel_consumption=row.get("fuel_consumption"),
                battery_voltage=row.get("battery_voltage"),
                tire_pressure=row.get("tire_pressure"),
                speed=row.get("speed"),
                engine_load=row.get("engine_load"),
                failure_label=int(row.get("failure_label", 0))
                if pd.notna(row.get("failure_label"))
                else 0,
            )
            records.append(reading)
        session.bulk_save_objects(records)
        session.commit()
        return len(records)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@cached(ttl=10)
def get_sensor_readings(
    vehicle_id: int,
    user_id: int,
    upload_id: int | None = None,
    limit: int | None = None,
):
    """Get sensor readings as a list of dicts. Optionally filter by upload and limit rows."""
    import pandas as pd

    session = get_session()
    try:
        query = session.query(SensorReading).filter_by(
            vehicle_id=vehicle_id, user_id=user_id
        )
        if upload_id:
            query = query.filter_by(upload_id=upload_id)

        # When limiting, fetch newest rows first then reverse to keep ascending order
        if limit is not None:
            query = query.order_by(SensorReading.timestamp.desc()).limit(limit)
            readings = list(reversed(query.all()))
        else:
            query = query.order_by(SensorReading.timestamp.asc())
            readings = query.all()

        if not readings:
            return pd.DataFrame()

        data = []
        for r in readings:
            data.append(
                {
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "engine_temp": r.engine_temp,
                    "oil_pressure": r.oil_pressure,
                    "coolant_temp": r.coolant_temp,
                    "engine_rpm": r.engine_rpm,
                    "vibration": r.vibration,
                    "fuel_consumption": r.fuel_consumption,
                    "battery_voltage": r.battery_voltage,
                    "tire_pressure": r.tire_pressure,
                    "speed": r.speed,
                    "engine_load": r.engine_load,
                    "failure_label": r.failure_label,
                }
            )
        return pd.DataFrame(data)
    finally:
        session.close()


def get_uploads_for_vehicle(vehicle_id: int, user_id: int) -> list[SensorUpload]:
    """Get all uploads for a vehicle."""
    session = get_session()
    try:
        return (
            session.query(SensorUpload)
            .filter_by(vehicle_id=vehicle_id, user_id=user_id)
            .order_by(SensorUpload.upload_time.desc())
            .all()
        )
    finally:
        session.close()


# ──────────────────────────────────────────────
# Trained Model CRUD
# ──────────────────────────────────────────────


def save_trained_model(
    user_id: int,
    vehicle_id: int,
    model_name: str,
    model_path: str,
    scaler_path: str,
    metrics: dict,
    is_best: bool = False,
) -> TrainedModel:
    """Save trained model metadata."""
    session = get_session()
    try:
        tm = TrainedModel(
            user_id=user_id,
            vehicle_id=vehicle_id,
            model_name=model_name,
            model_path=model_path,
            scaler_path=scaler_path,
            accuracy=metrics.get("accuracy"),
            precision_score=metrics.get("precision"),
            recall=metrics.get("recall"),
            f1=metrics.get("f1"),
            roc_auc=metrics.get("roc_auc"),
            is_best=is_best,
        )
        session.add(tm)
        session.commit()
        session.refresh(tm)
        return tm
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_best_model(user_id: int, vehicle_id: int | None = None) -> TrainedModel | None:
    """Get the current best model for a user (optionally per vehicle)."""
    session = get_session()
    try:
        query = session.query(TrainedModel).filter_by(user_id=user_id, is_best=True)
        if vehicle_id:
            query = query.filter_by(vehicle_id=vehicle_id)
        return query.order_by(TrainedModel.trained_at.desc()).first()
    finally:
        session.close()


@cached(ttl=10)
def get_all_trained_models(user_id: int) -> list[TrainedModel]:
    """Get all trained models for a user."""
    session = get_session()
    try:
        return (
            session.query(TrainedModel)
            .filter_by(user_id=user_id)
            .order_by(TrainedModel.trained_at.desc())
            .all()
        )
    finally:
        session.close()


def clear_best_model_flags(user_id: int):
    """Clear all best-model flags for a user before setting a new one."""
    session = get_session()
    try:
        session.query(TrainedModel).filter_by(user_id=user_id, is_best=True).update(
            {"is_best": False}
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def set_champion_model(model_id: int, user_id: int) -> bool:
    """Set a model as champion (un-sets any existing champion for the user)."""
    session = get_session()
    try:
        session.query(TrainedModel).filter_by(user_id=user_id, is_champion=True).update(
            {"is_champion": False}
        )
        model = (
            session.query(TrainedModel).filter_by(id=model_id, user_id=user_id).first()
        )
        if not model:
            return False
        model.is_champion = True
        session.commit()
        log_audit(
            user_id,
            "model_promoted",
            "TrainedModel",
            model_id,
            f"Model {model.model_name} promoted to champion",
        )
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_champion_model(
    user_id: int, vehicle_id: int | None = None
) -> TrainedModel | None:
    """Get the current champion model for a user (optionally per vehicle)."""
    session = get_session()
    try:
        query = session.query(TrainedModel).filter_by(user_id=user_id, is_champion=True)
        if vehicle_id:
            query = query.filter_by(vehicle_id=vehicle_id)
        return query.order_by(TrainedModel.trained_at.desc()).first()
    finally:
        session.close()


# ──────────────────────────────────────────────
# Prediction CRUD
# ──────────────────────────────────────────────


def save_prediction(
    user_id: int,
    vehicle_id: int,
    model_id: int,
    prediction: str,
    failure_prob: float,
    health_score: float,
    top_features: str,
) -> Prediction:
    """Save a prediction result."""
    session = get_session()
    try:
        pred = Prediction(
            user_id=user_id,
            vehicle_id=vehicle_id,
            model_id=model_id,
            prediction=prediction,
            failure_prob=failure_prob,
            health_score=health_score,
            top_features=top_features,
        )
        session.add(pred)
        session.commit()
        session.refresh(pred)
        return pred
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_predictions_for_vehicle(vehicle_id: int, user_id: int) -> list[Prediction]:
    """Get all predictions for a vehicle."""
    session = get_session()
    try:
        return (
            session.query(Prediction)
            .filter_by(vehicle_id=vehicle_id, user_id=user_id)
            .order_by(Prediction.predicted_at.desc())
            .all()
        )
    finally:
        session.close()


@cached(ttl=10)
def get_latest_prediction(vehicle_id: int, user_id: int) -> Prediction | None:
    """Get the most recent prediction for a vehicle."""
    session = get_session()
    try:
        return (
            session.query(Prediction)
            .filter_by(vehicle_id=vehicle_id, user_id=user_id)
            .order_by(Prediction.predicted_at.desc())
            .first()
        )
    finally:
        session.close()


def get_latest_predictions_for_user(user_id: int) -> dict[int, Prediction]:
    """Get the latest prediction per vehicle for a user (batch)."""
    from sqlalchemy import func

    session = get_session()
    try:
        # Subquery: max predicted_at per vehicle for this user
        subq = (
            session.query(
                Prediction.vehicle_id,
                func.max(Prediction.predicted_at).label("max_predicted_at"),
            )
            .filter_by(user_id=user_id)
            .group_by(Prediction.vehicle_id)
            .subquery()
        )
        rows = (
            session.query(Prediction)
            .join(
                subq,
                (Prediction.vehicle_id == subq.c.vehicle_id)
                & (Prediction.predicted_at == subq.c.max_predicted_at),
            )
            .all()
        )
        return {r.vehicle_id: r for r in rows}
    finally:
        session.close()


# ──────────────────────────────────────────────
# Maintenance History CRUD
# ──────────────────────────────────────────────


def create_maintenance_record(
    vehicle_id: int,
    user_id: int,
    service_date,
    service_type: str,
    parts_replaced: str | None = None,
    cost: float | None = None,
    notes: str | None = None,
) -> MaintenanceHistory:
    """Create a maintenance history record."""
    session = get_session()
    try:
        record = MaintenanceHistory(
            vehicle_id=vehicle_id,
            user_id=user_id,
            service_date=service_date,
            service_type=service_type,
            parts_replaced=parts_replaced,
            cost=cost,
            notes=notes,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_maintenance_history(vehicle_id: int, user_id: int) -> list[MaintenanceHistory]:
    """Get maintenance history for a vehicle."""
    session = get_session()
    try:
        return (
            session.query(MaintenanceHistory)
            .filter_by(vehicle_id=vehicle_id, user_id=user_id)
            .order_by(MaintenanceHistory.service_date.desc())
            .all()
        )
    finally:
        session.close()


def update_maintenance_record(record_id: int, user_id: int, **kwargs) -> bool:
    """Update a maintenance record. Returns True if updated."""
    session = get_session()
    try:
        record = (
            session.query(MaintenanceHistory)
            .filter_by(id=record_id, user_id=user_id)
            .first()
        )
        if not record:
            return False
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_maintenance_record(record_id: int, user_id: int) -> bool:
    """Delete a maintenance record. Returns True if deleted."""
    session = get_session()
    try:
        record = (
            session.query(MaintenanceHistory)
            .filter_by(id=record_id, user_id=user_id)
            .first()
        )
        if not record:
            return False
        session.delete(record)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ──────────────────────────────────────────────
# Alert CRUD
# ──────────────────────────────────────────────


def _make_alert_fingerprint(
    vehicle_id: int, alert_type: str, sensor_value: float | None = None
) -> str:
    """
    Create a deterministic fingerprint for alert deduplication.

    The fingerprint is a hash of ``vehicle_id:alert_type:value_bucket``.
    The value is rounded to the nearest 5 (i.e. bucketed) so that small
    fluctuations don't create separate alert groups.  When no sensor value
    is available (e.g. ``failure_prob_above`` rules), ``none`` is used.
    """
    bucket = int(round(sensor_value / 5.0)) * 5 if sensor_value is not None else "none"
    raw = f"{vehicle_id}:{alert_type}:{bucket}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_recent_alert(fingerprint: str, minutes: int = 30) -> Alert | None:
    """
    Check if an alert with the given fingerprint was created within the
    last ``minutes`` minutes. Returns the alert if found, else None.
    """
    session = get_session()
    try:
        cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            minutes=minutes
        )
        return (
            session.query(Alert)
            .filter(
                Alert.alert_fingerprint == fingerprint,
                Alert.created_at >= cutoff,
            )
            .order_by(Alert.created_at.desc())
            .first()
        )
    finally:
        session.close()


def create_alert(
    vehicle_id: int,
    user_id: int,
    alert_type: str,
    severity: str,
    message: str,
    sensor_value: float | None = None,
) -> Alert | None:
    """
    Create an alert with deduplication.

    If the same alert fingerprint exists within the last 30 minutes,
    the duplicate is skipped and None is returned.

    Args:
        vehicle_id: Vehicle ID.
        user_id: User ID.
        alert_type: Short type string (e.g. "high_engine_temp").
        severity: "High", "Medium", or "Low".
        message: Human-readable alert message.
        sensor_value: Optional current sensor reading (used for fingerprint).

    Returns:
        The Alert object if created, or None if a recent duplicate was found.
    """
    fingerprint = _make_alert_fingerprint(
        vehicle_id, alert_type, sensor_value=sensor_value
    )

    # Dedup: skip if same fingerprint fired in the last 30 minutes
    existing = get_recent_alert(fingerprint, minutes=30)
    if existing:
        return None

    session = get_session()
    try:
        alert = Alert(
            vehicle_id=vehicle_id,
            user_id=user_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            alert_fingerprint=fingerprint,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return alert
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@cached(ttl=10)
def get_active_alerts(user_id: int, vehicle_id: int | None = None) -> list[Alert]:
    """Get non-dismissed alerts for a user."""
    session = get_session()
    try:
        query = session.query(Alert).filter_by(user_id=user_id, is_dismissed=False)
        if vehicle_id:
            query = query.filter_by(vehicle_id=vehicle_id)
        return query.order_by(Alert.created_at.desc()).all()
    finally:
        session.close()


def get_all_alerts(user_id: int, vehicle_id: int | None = None) -> list[Alert]:
    """Get all alerts (including dismissed) for a user."""
    session = get_session()
    try:
        query = session.query(Alert).filter_by(user_id=user_id)
        if vehicle_id:
            query = query.filter_by(vehicle_id=vehicle_id)
        return query.order_by(Alert.created_at.desc()).all()
    finally:
        session.close()


def dismiss_alert(alert_id: int, user_id: int) -> bool:
    """Dismiss an alert. Returns True if dismissed."""
    session = get_session()
    try:
        alert = session.query(Alert).filter_by(id=alert_id, user_id=user_id).first()
        if not alert:
            return False
        alert.is_dismissed = True
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ──────────────────────────────────────────────
# Audit log
# ──────────────────────────────────────────────


def log_audit(
    user_id: int,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: str | None = None,
) -> AuditLog:
    """Record a critical action in the audit log."""
    session = get_session()
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_audit_logs(user_id: int | None = None, limit: int = 100) -> list[AuditLog]:
    """Get audit log entries, optionally filtered by user."""
    session = get_session()
    try:
        query = session.query(AuditLog)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    finally:
        session.close()


# ──────────────────────────────────────────────
# Organization CRUD
# ──────────────────────────────────────────────


def create_organization(name: str, plan: str = "free") -> Organization | None:
    """Create a new organization."""
    session = get_session()
    try:
        existing = session.query(Organization).filter_by(name=name).first()
        if existing:
            return None
        org = Organization(name=name, plan=plan)
        session.add(org)
        session.commit()
        session.refresh(org)
        return org
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_organization(org_id: int) -> Organization | None:
    """Get organization by ID."""
    session = get_session()
    try:
        return session.query(Organization).filter_by(id=org_id).first()
    finally:
        session.close()


def get_all_organizations() -> list[Organization]:
    """List all organizations (admin use)."""
    session = get_session()
    try:
        return (
            session.query(Organization).order_by(Organization.created_at.desc()).all()
        )
    finally:
        session.close()


# ──────────────────────────────────────────────
# User management (admin)
# ──────────────────────────────────────────────


def update_user_role(user_id: int, new_role: str) -> bool:
    """Update a user's role."""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False
        user.role = new_role
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_all_users(organization_id: int | None = None) -> list[User]:
    """Get all users, optionally filtered by organization."""
    session = get_session()
    try:
        query = session.query(User)
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        return query.order_by(User.created_at.desc()).all()
    finally:
        session.close()


def deactivate_user(user_id: int) -> bool:
    """Deactivate a user (soft delete)."""
    session = get_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False
        user.is_active = False
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_all_predictions_for_user(user_id: int) -> list[Prediction]:
    """Get all predictions across all vehicles for a user."""
    session = get_session()
    try:
        return (
            session.query(Prediction)
            .filter_by(user_id=user_id)
            .order_by(Prediction.predicted_at.desc())
            .all()
        )
    finally:
        session.close()


# ──────────────────────────────────────────────
# Alert escalation CRUD
# ──────────────────────────────────────────────


def acknowledge_alert(alert_id: int, user_id: int, acknowledged_by: int) -> bool:
    """Mark an alert as acknowledged by a specific user."""
    session = get_session()
    try:
        alert = session.query(Alert).filter_by(id=alert_id, user_id=user_id).first()
        if not alert:
            return False
        alert.acknowledged_at = datetime.datetime.now(datetime.UTC)
        alert.acknowledged_by = acknowledged_by
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_unacknowledged_high_alerts(
    user_id: int, vehicle_id: int, since_minutes: int = 15
) -> list[Alert]:
    """Get High-severity alerts not acknowledged in ``since_minutes``."""
    session = get_session()
    try:
        cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            minutes=since_minutes
        )
        return (
            session.query(Alert)
            .filter(
                Alert.vehicle_id == vehicle_id,
                Alert.user_id == user_id,
                Alert.severity == "High",
                Alert.acknowledged_at.is_(None),
                Alert.created_at <= cutoff,
            )
            .order_by(Alert.created_at.asc())
            .all()
        )
    finally:
        session.close()


def count_alerts_last_hour(vehicle_id: int, user_id: int) -> int:
    """Count high-severity alerts for a vehicle in the last hour."""
    session = get_session()
    try:
        cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        return (
            session.query(Alert)
            .filter(
                Alert.vehicle_id == vehicle_id,
                Alert.user_id == user_id,
                Alert.severity == "High",
                Alert.created_at >= cutoff,
            )
            .count()
        )
    finally:
        session.close()


# ──────────────────────────────────────────────
# Incident CRUD
# ──────────────────────────────────────────────


def create_incident(
    vehicle_id: int,
    user_id: int,
    title: str,
    severity: str = "High",
    description: str | None = None,
    related_alert_ids: list[int] | None = None,
) -> Incident | None:
    """Create a critical incident ticket."""
    session = get_session()
    try:
        inc = Incident(
            vehicle_id=vehicle_id,
            user_id=user_id,
            title=title,
            description=description,
            severity=severity,
            related_alert_ids=json.dumps(related_alert_ids or []),
        )
        session.add(inc)
        session.commit()
        session.refresh(inc)
        return inc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_open_incidents(user_id: int) -> list[Incident]:
    """Get all incidents for a user, newest first."""
    session = get_session()
    try:
        return (
            session.query(Incident)
            .filter_by(user_id=user_id)
            .order_by(Incident.created_at.desc())
            .all()
        )
    finally:
        session.close()


def resolve_incident(
    incident_id: int, user_id: int, resolution_notes: str | None = None
) -> bool:
    """Mark an incident as resolved."""
    session = get_session()
    try:
        inc = session.query(Incident).filter_by(id=incident_id, user_id=user_id).first()
        if not inc:
            return False
        inc.status = "resolved"
        inc.resolved_at = datetime.datetime.now(datetime.UTC)
        if resolution_notes:
            inc.resolution_notes = resolution_notes
        session.commit()
        return True
    finally:
        session.close()


# ──────────────────────────────────────────────
# Notification Preferences CRUD
# ──────────────────────────────────────────────


def get_notification_prefs(user_id: int) -> NotificationPreferences | None:
    """Get notification prefs, creating defaults if missing."""
    session = get_session()
    try:
        prefs = (
            session.query(NotificationPreferences).filter_by(user_id=user_id).first()
        )
        if prefs:
            return prefs
        prefs = NotificationPreferences(user_id=user_id)
        session.add(prefs)
        session.commit()
        session.refresh(prefs)
        return prefs
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ──────────────────────────────────────────────
# API Key CRUD
# ──────────────────────────────────────────────

import secrets


def hash_api_key(prefix: str, key: str) -> str:
    """Hash API key for storage."""
    return hashlib.sha256(f"{prefix}:{key}".encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key with prefix."""
    prefix = f"vhm_{secrets.token_urlsafe(8)}"
    key = secrets.token_urlsafe(32)
    return f"{prefix}.{key}", prefix


def create_api_key(
    user_id: int,
    name: str,
    scopes: list[str] | None = None,
    expires_days: int | None = None,
) -> tuple[APIKey, str]:
    """
    Create a new API key for a user.

    Returns (APIKey object, full_key_string).
    The full key is only shown once - store it securely!
    """
    session = get_session()
    try:
        full_key, prefix = generate_api_key()
        key_hash = hash_api_key(prefix, full_key.split(".", 1)[1])
        expires_at = (
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=expires_days)
            if expires_days
            else None
        )

        api_key = APIKey(
            user_id=user_id,
            name=name,
            prefix=prefix,
            key_hash=key_hash,
            scopes=json.dumps(scopes or ["read"]),
            expires_at=expires_at,
        )
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
        return api_key, full_key
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_api_keys_for_user(user_id: int) -> list[APIKey]:
    """List all API keys for a user (without the actual key)."""
    session = get_session()
    try:
        return (
            session.query(APIKey)
            .filter_by(user_id=user_id)
            .order_by(APIKey.created_at.desc())
            .all()
        )
    finally:
        session.close()


def get_api_key_by_id(key_id: int, user_id: int) -> APIKey | None:
    """Get a specific API key by ID."""
    session = get_session()
    try:
        return session.query(APIKey).filter_by(id=key_id, user_id=user_id).first()
    finally:
        session.close()


def revoke_api_key(key_id: int, user_id: int) -> bool:
    """Revoke (disable) an API key."""
    session = get_session()
    try:
        api_key = session.query(APIKey).filter_by(id=key_id, user_id=user_id).first()
        if not api_key:
            return False
        api_key.is_active = False
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_api_key(key_id: int, user_id: int) -> bool:
    """Permanently delete an API key."""
    session = get_session()
    try:
        api_key = session.query(APIKey).filter_by(id=key_id, user_id=user_id).first()
        if not api_key:
            return False
        session.delete(api_key)
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_or_create_default_upload(vehicle_id: int, user_id: int) -> int:
    """Get or create a default SensorUpload record for live telemetry ingestion."""
    session = get_session()
    try:
        upload = session.query(SensorUpload).filter_by(
            vehicle_id=vehicle_id,
            user_id=user_id,
            filename="live_telemetry_stream"
        ).first()
        if not upload:
            import datetime
            upload = SensorUpload(
                vehicle_id=vehicle_id,
                user_id=user_id,
                filename="live_telemetry_stream",
                row_count_raw=0,
                row_count_clean=0,
                upload_time=datetime.datetime.utcnow()
            )
            session.add(upload)
            session.commit()
            session.refresh(upload)
        return upload.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

