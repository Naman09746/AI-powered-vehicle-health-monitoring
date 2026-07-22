"""
Health check and Prometheus metrics for the Vehicle Health Monitor.

Provides:
- ``/health`` endpoint (FastAPI route, already in api/main.py)
- Prometheus metric collectors (for production with prometheus_client)
- ``db_size()`` helper for checking DB health
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logger import get_logger

log = get_logger("monitoring")

_HAS_PROMETHEUS = False
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest

    _HAS_PROMETHEUS = True
except ImportError:
    pass


# ── Metric definitions (no-op stubs when prometheus_client is absent) ──


class _StubMetric:
    """No-op stub so code doesn't crash when prometheus_client is missing."""

    def labels(self, **kwargs):
        return self

    def inc(self, amount=1):
        pass

    def observe(self, amount):
        pass

    def set(self, value):
        pass

    def set_function(self, func):
        pass


# Predictions
predictions_total = (
    Counter(
        "vhm_predictions_total",
        "Total predictions per vehicle",
        ["vehicle_id", "user_id"],
    )
    if _HAS_PROMETHEUS
    else _StubMetric()
)

prediction_latency = (
    Histogram(
        "vhm_prediction_latency_seconds",
        "Model inference latency",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
    )
    if _HAS_PROMETHEUS
    else _StubMetric()
)

# Alerts
alerts_total = (
    Counter(
        "vhm_alerts_total",
        "Alert count by severity",
        ["severity"],
    )
    if _HAS_PROMETHEUS
    else _StubMetric()
)

# Data ingestion
ingestion_rate = (
    Gauge(
        "vhm_ingestion_readings_per_minute",
        "Sensor readings ingested per minute",
        ["vehicle_id"],
    )
    if _HAS_PROMETHEUS
    else _StubMetric()
)

# DB connection pool (PostgreSQL only)
db_pool_utilization = (
    Gauge(
        "vhm_db_pool_utilization",
        "DB connection pool usage (0-1)",
    )
    if _HAS_PROMETHEUS
    else _StubMetric()
)


def record_prediction(vehicle_id: int, user_id: int, latency: float) -> None:
    """Record a prediction event for Prometheus."""
    predictions_total.labels(vehicle_id=str(vehicle_id), user_id=str(user_id)).inc()
    prediction_latency.observe(latency)


def record_alert(severity: str) -> None:
    """Record an alert event for Prometheus."""
    alerts_total.labels(severity=severity).inc()


def get_prometheus_metrics() -> bytes:
    """Return Prometheus metrics in text format."""
    if _HAS_PROMETHEUS:
        return generate_latest()
    return b"# prometheus_client not installed"


def db_size(db_path: str = None) -> dict[str, Any]:
    """
    Check database file size and health.

    Args:
        db_path: Path to SQLite DB file (None for PostgreSQL).

    Returns:
        Dict with size_bytes, status, and last_check timestamp.
    """
    import os

    result = {
        "status": "unknown",
        "size_bytes": None,
        "last_check": datetime.now(UTC).isoformat(),
    }

    # SQLite — check file size
    if db_path and os.path.exists(db_path):
        size = os.path.getsize(db_path)
        result["size_bytes"] = size
        result["size_mb"] = round(size / (1024 * 1024), 2)
        result["status"] = "ok"
    else:
        # PostgreSQL — check via query
        try:
            import core.db as database

            session = database.get_session()
            session.execute(database.text("SELECT 1"))
            session.close()
            result["status"] = "ok"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

    return result


def check_redis(redis_url: str = None) -> dict[str, Any]:
    """
    Check Redis connectivity.

    Args:
        redis_url: Redis connection URL. Defaults to config.REDIS_URL.

    Returns:
        Dict with status, ping_ms, and version.
    """
    from core.config import REDIS_URL as CFG_REDIS_URL

    url = redis_url or CFG_REDIS_URL
    result = {"status": "unknown", "url": url}

    try:
        import redis as redis_client

        r = redis_client.from_url(url, socket_connect_timeout=3)
        info = r.info()
        result["status"] = "ok"
        result["version"] = info.get("redis_version", "unknown")
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    return result


def check_mqtt(broker: str = "localhost", port: int = 1883) -> dict[str, Any]:
    """
    Check MQTT broker connectivity.

    Args:
        broker: MQTT broker hostname.
        port: MQTT broker port.

    Returns:
        Dict with status.
    """
    result = {"status": "unknown", "broker": broker, "port": port}

    try:
        import paho.mqtt.client as mqtt

        client = mqtt.Client(client_id="vhm-healthcheck")
        client.connect(broker, port, keepalive=5)
        client.disconnect()
        result["status"] = "ok"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    return result
