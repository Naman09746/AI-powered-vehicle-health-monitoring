"""
Automated data cleanup and retention pruning task.
Prunes historical sensor readings older than DATA_RETENTION_DAYS (default: 90 days)
to keep free database storage clean and performant.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete

import core.db as database
from core.logger import get_logger

log = get_logger("tasks.cleanup")

RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "90"))


def run_cleanup(retention_days: int = RETENTION_DAYS) -> dict[str, int | str]:
    """
    Deletes sensor readings older than retention_days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    session = database.get_session()

    try:
        stmt = delete(database.SensorReading).where(database.SensorReading.timestamp < cutoff)
        result = session.execute(stmt)
        session.commit()

        deleted_count = result.rowcount
        log.info("Data cleanup complete: pruned %d readings older than %s", deleted_count, cutoff.isoformat())

        return {
            "status": "success",
            "deleted_readings": deleted_count,
            "cutoff_timestamp": cutoff.isoformat(),
            "retention_days": retention_days,
        }
    except Exception as exc:
        session.rollback()
        log.error("Data cleanup failed: %s", exc)
        return {"status": "error", "message": str(exc)}
    finally:
        session.close()


if __name__ == "__main__":
    res = run_cleanup()
    print("Cleanup result:", res)
