# ──────────────────────────────────────────────
# Vehicle Health Monitor — Dockerfile
# Multi-stage build: shared deps, then API / Celery / MQTT images
# ──────────────────────────────────────────────

FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies for psycopg2, scipy, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (leverage Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# ── API server ────────────────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Celery worker ─────────────────────────────────────────────────────────────
FROM base AS celery
CMD ["celery", "-A", "tasks.retrain_task", "worker", "-l", "info"]

# ── MQTT subscriber ───────────────────────────────────────────────────────────
FROM base AS mqtt
CMD ["python", "ingest/mqtt_subscriber.py"]

# ── Default target ────────────────────────────────────────────────────────────
FROM base
CMD ["python", "-c", "print('Use one of: api, celery, mqtt as target')"]
