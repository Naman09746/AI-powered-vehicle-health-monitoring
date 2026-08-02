"""
Audit Trail Logging module.
Records security and governance actions in the database audit log.
"""

from __future__ import annotations

import json
from typing import Any
import core.db as database
from core.logger import get_logger

log = get_logger("audit")


def log_audit_event(
    user_id: int,
    action: str,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> bool:
    """
    Records an audit log entry.
    """
    session = database.get_session()
    try:
        entry = database.AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=json.dumps(details) if details else None,
        )
        session.add(entry)
        session.commit()
        log.info("Audit log: user=%d action=%s resource=%s:%s", user_id, action, resource_type, resource_id)
        return True
    except Exception as exc:
        session.rollback()
        log.error("Failed to write audit log: %s", exc)
        return False
    finally:
        session.close()
