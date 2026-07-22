"""
OpenTelemetry instrumentation for the Vehicle Health API.

Sets up:
  - Distributed tracing via OTLP exporter (gRPC)
  - Auto-instrumentation for FastAPI, SQLAlchemy, httpx, and redis
  - Prometheus /metrics endpoint for RED metrics
  - Custom span attributes for ``vehicle_id`` and ``user_id``

Gracefully handles missing packages — importing this module is safe even
when OpenTelemetry is not installed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from core.config import OTEL_EXPORTER_OTLP_ENDPOINT

log = logging.getLogger("api.telemetry")

# Sentinel — tracks whether telemetry has been loaded for this process.
_telemetry_loaded: bool = False


# ── Public API ───────────────────────────────────────────────────


def setup_telemetry(app: Any = None) -> bool:
    """Initialise OpenTelemetry + Prometheus instrumentation.

    Call once during FastAPI lifespan startup (before *yield*).

    Parameters
    ----------
    app : FastAPI or None
        The FastAPI application instance.  When provided, the FastAPI
        instrumentor and Prometheus ``/metrics`` endpoint are set up
        automatically.

    Returns
    -------
    bool
        ``True`` if all telemetry was loaded, ``False`` if packages
        were missing (application continues without crashing).
    """
    global _telemetry_loaded
    if _telemetry_loaded:
        return True

    try:
        _do_setup_otel(app)
        _setup_prometheus(app)
        _telemetry_loaded = True
        log.info("OpenTelemetry + Prometheus instrumentation initialised")
        return True
    except ImportError as exc:
        log.warning(
            "Telemetry packages not available — observability disabled (%s)", exc
        )
        return False
    except Exception as exc:
        log.warning("Failed to initialise telemetry: %s", exc)
        return False


def set_span_attributes(
    vehicle_id: int | str | None = None,
    user_id: int | str | None = None,
) -> None:
    """Add custom attributes to the **current** OpenTelemetry span.

    Call from route handlers to enrich traces with domain context:

    .. code-block:: python

        set_span_attributes(vehicle_id=vehicle.pk, user_id=current_user.id)

    Safe to call even when OpenTelemetry is not loaded (no-op).
    """
    if not _telemetry_loaded:
        return
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            if vehicle_id is not None:
                span.set_attribute("vehicle_id", str(vehicle_id))
            if user_id is not None:
                span.set_attribute("user_id", str(user_id))
    except Exception:
        pass


# ── OTel Tracing ─────────────────────────────────────────────────


def _do_setup_otel(app: Any = None) -> None:
    """Configure the OTel TracerProvider and auto-instrumentors.

    Raises ``ImportError`` if core OpenTelemetry packages are absent.
    """
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # ── Resource ─────────────────────────────────────────────────
    resource = Resource.create(
        {
            "service.name": "vehicle-health-api",
            "service.version": "3.0.0",
        }
    )

    # ── Provider ─────────────────────────────────────────────────
    provider = TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(
        endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)

    # ── FastAPI instrumentation ──────────────────────────────────
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    # ── Library auto-instrumentation ─────────────────────────────
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)

    # SQLAlchemy — needs the engine instance (already created in api.database).
    # We import it here to avoid circular imports at module level.
    try:
        from api.database import engine

        SQLAlchemyInstrumentor().instrument(
            engine=engine,
            tracer_provider=provider,
        )
        log.info("SQLAlchemy engine instrumented")
    except Exception:
        log.warning("Could not instrument SQLAlchemy engine (import or setup failed)")

    # Store on app so route handlers can retrieve the tracer if needed.
    if app is not None:
        app.state.tracer_provider = provider
        app.state.tracer = trace.get_tracer("vehicle-health-api", "3.0.0")

    log.info(
        "OTLP trace exporter configured — endpoint: %s", OTEL_EXPORTER_OTLP_ENDPOINT
    )

    # ── Middleware: enrich spans with user_id from request state ─
    if app is not None:
        _add_trace_enrich_middleware(app)


def _add_trace_enrich_middleware(app: Any) -> None:
    """Starlette middleware that adds ``user_id`` to the active span."""

    @app.middleware("http")
    async def _enrich_traces(request: Any, call_next: Any) -> Any:
        from opentelemetry import trace as otel_trace

        response = await call_next(request)

        try:
            span = otel_trace.get_current_span()
            if span.is_recording():
                # user_id may have been set by auth middleware in request.state
                uid = getattr(request.state, "user_id", None)
                if uid is not None:
                    span.set_attribute("user_id", str(uid))

                # vehicle_id from path parameter if present
                path_params = getattr(request, "path_params", {}) or {}
                vid = path_params.get("vehicle_id")
                if vid is not None:
                    span.set_attribute("vehicle_id", str(vid))
        except Exception:
            pass

        return response


# ── Prometheus Metrics ───────────────────────────────────────────


def _setup_prometheus(app: Any = None) -> None:
    """Expose Prometheus ``/metrics`` endpoint and register RED metric collectors.

    Raises ``ImportError`` if ``prometheus_client`` is not installed.
    """
    from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

    # ── Define metric collectors (auto-registered with the default registry) ──
    http_requests_total = Counter(
        "http_requests_total",
        "Total count of HTTP requests",
        ["method", "endpoint", "status"],
    )

    http_request_duration_seconds = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    active_vehicles = Gauge(
        "active_vehicles",
        "Number of vehicles currently being monitored",
    )

    ml_training_total = Counter(
        "ml_training_total",
        "Total number of ML model training runs executed",
    )

    # ── Mount the ``/metrics`` ASGI app ──────────────────────────
    if app is not None:
        metrics_asgi = make_asgi_app()
        app.mount("/metrics", metrics_asgi)
        log.info("Prometheus /metrics endpoint mounted")

    # ── Request-tracking middleware ──────────────────────────────
    if app is not None:

        @app.middleware("http")
        async def _track_http_metrics(request: Any, call_next: Any) -> Any:
            method = request.method
            endpoint = request.url.path
            start = time.perf_counter()

            response = await call_next(request)

            duration = time.perf_counter() - start
            status = str(response.status_code)

            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status,
            ).inc()
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            return response

    # ── Expose metric references on app.state for domain updates ─
    if app is not None:
        app.state.metrics = {
            "http_requests_total": http_requests_total,
            "http_request_duration_seconds": http_request_duration_seconds,
            "active_vehicles": active_vehicles,
            "ml_training_total": ml_training_total,
        }
