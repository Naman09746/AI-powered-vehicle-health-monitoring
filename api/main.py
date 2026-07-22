"""
FastAPI application entry-point for the Vehicle Health Monitor API.

Run with::

    uvicorn api.main:app --reload --port 8000

Or via the Makefile::

    make api
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from core.config import APP_CONFIG, REDIS_URL
from core.logger import get_logger

log = get_logger("api")


# ── Lifespan (startup / shutdown) ──────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Async lifespan — initialises DB pool, Redis, ML models on startup."""
    log.info("Starting up — initialising connections")

    # Database
    from api.database import engine, init_db
    from core.config import DATABASE_URL

    log.info(
        "Using database URL: %s",
        DATABASE_URL[:40] + "..." if len(DATABASE_URL) > 40 else DATABASE_URL,
    )
    try:
        await init_db()
        log.info("Database tables verified")
    except Exception:
        log.warning("Could not init DB tables (may already exist)")

    # OpenTelemetry instrumentation (safe no-op if packages absent)
    from api.telemetry import setup_telemetry

    setup_telemetry(app)
    log.info("Telemetry setup complete")

    # Redis connection pool
    redis_client = None
    if REDIS_URL and REDIS_URL != "redis://localhost:6379/0":
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(
                REDIS_URL,
                socket_connect_timeout=3,
                socket_keepalive=True,
                max_connections=20,
                decode_responses=True,
            )
            await redis_client.ping()
            app.state.redis = redis_client
            log.info("Redis connection pool established")
        except Exception:
            log.warning("Redis not reachable — will retry on demand")
            app.state.redis = None

    # ML Model registry cache (load champion models into memory)
    try:
        from core.db import TrainedModel, get_session

        session = get_session()
        try:
            champions = session.query(TrainedModel).filter_by(is_champion=True).all()
            model_cache = {}
            for m in champions:
                if m.model_path and m.scaler_path:
                    import joblib

                    model_cache[f"{m.vehicle_id}_{m.user_id}"] = {
                        "model": joblib.load(m.model_path),
                        "scaler": joblib.load(m.scaler_path),
                        "feature_columns": m.feature_columns_json,
                        "version": m.model_version,
                    }
            app.state.model_cache = model_cache
            log.info("Loaded %d champion models into cache", len(model_cache))
        finally:
            session.close()
    except Exception:
        log.warning("Could not preload ML models — will load on demand")
        app.state.model_cache = {}

    # Store for access in routers
    app.state.redis_client = redis_client

    yield  # ── App runs here ──

    # Shutdown
    log.info("Shutting down — closing connections")
    if redis_client:
        await redis_client.aclose()
        log.info("Redis connection pool closed")
    await engine.dispose()
    log.info("Database connections closed")


# ── FastAPI app ───────────────────────────────────────────────

app = FastAPI(
    title=APP_CONFIG["page_title"] + " API",
    description="REST + WebSocket API for the Vehicle Health Monitor. "
    "Supports real-time sensor ingestion, ML predictions, "
    "alert management, and PDF report generation.",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    contact={
        "name": "Vehicle Health Monitor Support",
        "email": "support@vehiclehealth.example.com",
        "url": "https://vehiclehealth.example.com/support",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
        {
            "url": "https://api.staging.vehiclehealth.example.com",
            "description": "Staging",
        },
        {"url": "https://api.vehiclehealth.example.com", "description": "Production"},
    ],
)

# ── Middleware & error handlers ────────────────────────────────

from api.middleware import setup_middleware

setup_middleware(app)

# ── Include routers ──────────────────────────────────────────

from api.health import router as health_router
from api.routers import (
    alerts,
    apikeys,
    auth,
    copilot,
    dashboard,
    fleet,
    history,
    ml,
    organizations,
    predictions,
    readings,
    recommendations,
    reports,
    simulator,
    uploads,
    vehicles,
    webhooks,
)

app.include_router(health_router)
app.include_router(auth.router)
app.include_router(apikeys.router)
app.include_router(vehicles.router)
app.include_router(readings.router)
app.include_router(predictions.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(ml.router)
app.include_router(organizations.router)
app.include_router(uploads.router)
app.include_router(copilot.router)
app.include_router(dashboard.router)
app.include_router(fleet.router)
app.include_router(history.router)
app.include_router(recommendations.router)
app.include_router(simulator.router)
app.include_router(webhooks.router)

# ── Custom OpenAPI schema ─────────────────────────────────────

from api.openapi import custom_openapi

app.openapi = custom_openapi  # type: ignore[method-assign]

# ── API versioning ──────────────────────────────────────────

from api.api_version import DeprecatedApiVersion, deprecated_api_version_handler

app.add_exception_handler(DeprecatedApiVersion, deprecated_api_version_handler)

# ── WebSocket ────────────────────────────────────────────────

from api.websocket import vehicle_live_feed


@app.websocket("/ws/vehicles/{vehicle_id}/live")
async def ws_vehicle_live(websocket: WebSocket, vehicle_id: int):
    """WebSocket endpoint for real-time vehicle sensor feed."""
    await vehicle_live_feed(websocket, vehicle_id)


# ── Root ─────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "service": APP_CONFIG["page_title"] + " API",
        "version": "3.0.0",
        "docs": "/api/docs",
    }
