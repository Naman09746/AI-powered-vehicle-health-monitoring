"""
Read replica connection pool for dashboard and reporting queries.

Provides a separate async engine that points to a read replica of the
primary database.  Dashboard routers, report generators, and other
read-heavy workloads should use ``get_read_only_db()`` instead of the
default ``get_db()`` dependency to offload the primary.

Configuration
-------------
Set ``DATABASE_URL_READ_ONLY`` in the environment (or ``.env`` file):

    DATABASE_URL_READ_ONLY=postgresql+asyncpg://user:pass@replica-host:5432/vehicle_health

When unset, the module falls back to ``DATABASE_URL`` (the primary database),
which makes it safe to use in development and single-node deployments.

Pool settings
-------------
The read-replica engine uses a larger pool than the primary (10-20
connections) because dashboard queries are typically long-running
aggregations that benefit from more concurrent connections.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import DATABASE_URL, DATABASE_URL_READ_ONLY

# ── Normalise URL ─────────────────────────────────────────────
_url = DATABASE_URL_READ_ONLY or DATABASE_URL
if _url.startswith("postgresql://") and "+asyncpg" not in _url:
    _url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)
if _url.startswith("sqlite"):
    _url = _url.replace("sqlite://", "sqlite+aiosqlite://", 1)

_is_sqlite = _url.startswith("sqlite+aiosqlite")

# ── Read-only engine ─────────────────────────────────────────
# The pool is deliberately larger than the primary's because the read
# replica's sole job is to serve concurrent dashboard/report queries.
_engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

read_only_engine = create_async_engine(_url, **_engine_kwargs)

ReadOnlySessionLocal = async_sessionmaker(
    bind=read_only_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_read_only_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async session that issues **read-only** queries.

    Unlike the primary session returned by ``get_async_session()``, this
    session does **not** commit on exit -- callers should only perform
    SELECT / read-only CTE queries.  Any write attempt will roll back
    on teardown.

    Usage::

        async with get_read_only_session() as session:
            result = await session.execute(select(Model).where(...))
    """
    async with ReadOnlySessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_only_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a read-only async session.

    Drop this into any router that serves dashboards, reports, or other
    read-heavy endpoints to offload the primary database.

    Example::

        from api.read_replica import get_read_only_db

        @router.get("/report")
        async def report(db: AsyncSession = Depends(get_read_only_db)):
            result = await db.execute(select(MyModel))
            ...
    """
    async with ReadOnlySessionLocal() as session:
        yield session


async def check_read_replica_conn() -> dict:
    """Quick health check for the read replica -- returns status and latency in ms."""
    import time

    t0 = time.perf_counter()
    try:
        async with ReadOnlySessionLocal() as s:
            await s.execute(text("SELECT 1"))
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        replica_type = "dedicated" if DATABASE_URL_READ_ONLY else "fallback (primary)"
        return {"status": "ok", "type": replica_type, "latency_ms": elapsed}
    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        return {"status": "error", "detail": str(exc), "latency_ms": elapsed}
