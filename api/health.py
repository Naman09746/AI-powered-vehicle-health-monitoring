"""
Liveness / Readiness probes for the FastAPI application.

Checks:
- Database connectivity (async)
- Redis connectivity (if REDIS_URL configured)
- ML model registry health (basic)
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from core.config import REDIS_URL

router = APIRouter(tags=["health"])


async def _check_db() -> dict:
    """Async database health check."""
    try:
        from api.database import check_db_conn

        return await check_db_conn()
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def _check_redis() -> dict:
    """Redis connectivity check."""
    if not REDIS_URL or REDIS_URL == "redis://localhost:6379/0":
        # Redis is optional in dev — report unavailable rather than failing
        return {"status": "not_configured"}
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def _check_ml() -> dict:
    """Check that ML model files are loadable."""
    try:
        from ml.ml_registry import registry

        models = registry.list_models()
        count = len(models)
        return {"status": "ok", "registered_models": count}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def _check_celery() -> dict:
    """Celery worker ping check (best-effort — optional dependency)."""
    try:
        from celery.app.control import Inspect

        from core.config import REDIS_URL

        if not REDIS_URL or REDIS_URL == "redis://localhost:6379/0":
            return {"status": "not_configured"}
        app = __import__("tasks.retrain_task", fromlist=["app"]).app
        inspect = Inspect(app=app)
        workers = inspect.ping()
        if workers:
            return {"status": "ok", "active_workers": len(workers)}
        return {"status": "degraded", "detail": "No Celery workers responded"}
    except ImportError:
        return {"status": "not_configured"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/health/live")
async def liveness() -> dict[str, Any]:
    """Liveness probe — always responds 200 if the process is alive."""
    return {
        "status": "alive",
        "service": "vehicle-health-monitor-api",
        "timestamp": time.time(),
    }


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """Readiness probe — checks DB, Redis, ML availability, and read replica."""
    start = time.perf_counter()

    db, redis, ml, celery = (
        await _check_db(),
        await _check_redis(),
        await _check_ml(),
        await _check_celery(),
    )

    # Check read replica
    try:
        from api.read_replica import check_read_replica_conn

        replica = await check_read_replica_conn()
    except ImportError:
        replica = {"status": "not_configured"}

    overall = "ok" if db["status"] == "ok" else "degraded"

    elapsed = round((time.perf_counter() - start) * 1000, 1)
    return {
        "status": overall,
        "checks": {
            "database": db,
            "read_replica": replica,
            "redis": redis,
            "celery": celery,
            "ml_registry": ml,
        },
        "uptime_seconds": _get_uptime(),
        "duration_ms": elapsed,
    }


@router.get("/health")
async def health_summary() -> dict[str, Any]:
    """Aggregated health summary (alias of /health/ready)."""
    return await readiness()


# ── Uptime tracking ────────────────────────────────────────────

_start_time = time.time()


def _get_uptime() -> float:
    return round(time.time() - _start_time, 1)
