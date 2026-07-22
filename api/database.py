"""
Async SQLAlchemy 2.0 engine and session factory for FastAPI.

Uses asyncpg driver -- falls back to aiosqlite for local dev without PostgreSQL.
Explicit connection pooling (5-20 connections) with recycle and pre-ping.

PgBouncer support
-----------------
When the environment variable ``DATABASE_URL_PGBOUNCER`` is set, it takes
precedence over ``DATABASE_URL`` for the async engine. This lets the app
route runtime queries through PgBouncer (port 6432) while Alembic / admin
scripts can still connect directly to PostgreSQL (port 5432).

Pool settings for PgBouncer (transaction mode):
  - ``pool_size`` is kept small (2-5 per worker) because PgBouncer already
    maintains a server-side connection pool. Each worker only needs enough
    connections for concurrent in-flight requests.
  - ``pool_pre_ping`` is disabled since PgBouncer handles stale connections.
  - ``pool_recycle`` can be raised or removed -- PgBouncer recycles for us.

See docker-compose.yml for the PgBouncer service definition.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import DATABASE_URL, ENV

# ── Naming convention for constraints (keeps Alembic happy) ──
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)

# ── Detect PgBouncer mode ────────────────────────────────────
# When DATABASE_URL_PGBOUNCER is set, the app runtime connections go through
# PgBouncer. The original DATABASE_URL is preserved for Alembic/admin tasks.
_PGBOUNCER_URL = os.getenv("DATABASE_URL_PGBOUNCER", "")
_USING_PGBOUNCER = bool(_PGBOUNCER_URL)

# ── Normalise URL ─────────────────────────────────────────────
# Prefer PgBouncer URL; fall back to the standard DATABASE_URL.
# If caller passes a sync postgresql:// URL, upgrade to asyncpg.
_url = _PGBOUNCER_URL or DATABASE_URL
if _url.startswith("postgresql://") and "+asyncpg" not in _url:
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)
if _url.startswith("sqlite"):
    _url = _url.replace("sqlite://", "sqlite+aiosqlite://", 1)

# ── Engine ────────────────────────────────────────────────────
_is_sqlite = _url.startswith("sqlite+aiosqlite")

_engine_kwargs: dict[str, Any] = {
    "echo": False,
    "pool_pre_ping": not _USING_PGBOUNCER,
    "pool_recycle": 7200 if _USING_PGBOUNCER else 3600,
}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 2 if _USING_PGBOUNCER else 5
    _engine_kwargs["max_overflow"] = 5 if _USING_PGBOUNCER else 15

engine = create_async_engine(_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async session and closes it on teardown."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_conn() -> dict:
    """Quick health check -- returns status and latency in ms."""
    import time

    t0 = time.perf_counter()
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        return {"status": "ok", "latency_ms": elapsed}
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        return {"status": "error", "detail": str(exc), "latency_ms": elapsed}


def run_migrations():
    """Run Alembic migrations programmatically to upgrade to head if needed."""
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    from core.logger import get_logger

    log = get_logger("db")

    # Path to alembic.ini in the root directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(base_dir, "alembic.ini")

    config = Config(ini_path)

    # Check current DB version vs head — skip if already up to date
    sync_url = DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
    engine = create_engine(sync_url)
    current = None
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current = ctx.get_current_revision()
    except Exception:
        # If database or alembic_version table doesn't exist, we'll let command.upgrade create it
        pass
    finally:
        engine.dispose()

    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()

    if current != head:
        log.info("Running migrations (current: %s, head: %s)...", current, head)
        command.upgrade(config, "head")
    else:
        log.info("Database already at head revision %s — skipping migration", head)


async def init_db():
    """Initialize database by running Alembic migrations and fallback to metadata.create_all."""
    from core.db import init_db as sync_init_db
    from core.logger import get_logger

    log = get_logger("db")

    if ENV != "test":
        try:
            import asyncio
            await asyncio.to_thread(run_migrations)
        except Exception as e:
            log.warning("Alembic migration warning (%s); applying create_all fallback", e)

    try:
        import asyncio
        await asyncio.to_thread(sync_init_db)
        log.info("Database schema verified (all tables created/verified)")
    except Exception as e:
        log.error("Failed to create_all tables: %s", e)
