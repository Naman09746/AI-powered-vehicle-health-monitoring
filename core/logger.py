"""
Structured JSON logging for the Vehicle Health Monitor.

Logs to:
  - Console (human-readable, colorized) at user-configured level
  - File (JSON lines) at DEBUG level for audit trail

Usage:
    from core.logger import get_logger
    log = get_logger(__name__)
    log.info("Training started", extra={"vehicle_id": 1, "model": "XGBoost"})
"""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from core.config import ENV, LOG_LEVEL

# Ensure logs directory exists
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines for the file handler."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "env": ENV,
        }
        # Include extra context if provided
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_entry.update(record.extra)
        # Include exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable colored output for the console handler."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red background
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        level_padded = record.levelname.ljust(8)
        # Ensure asctime is set (normally done by Formatter.format())
        if not hasattr(record, "asctime"):
            record.asctime = self.formatTime(record, self.datefmt)
        extra_str = ""
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            extra_str = " | " + json.dumps(record.extra, default=str)
        return (
            f"{color}{level_padded}{reset} | "
            f"{record.asctime} | {record.name}:{record.lineno} | "
            f"{record.getMessage()}{extra_str}"
        )


def _get_level() -> str:
    """Resolve log level from core.config, with env overrides."""
    return LOG_LEVEL.upper()


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Loggers are hierarchical: ``get_logger("db")`` and
    ``get_logger("db.queries")`` share the same handlers.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    level = _get_level()
    logger.setLevel(level)

    # ── Console handler (respects LOG_LEVEL) ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ConsoleFormatter(datefmt="%H:%M:%S")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # ── File handler (always DEBUG for full audit trail) ──
    log_file = LOGS_DIR / f"vhm_{datetime.now().strftime('%Y%m%d')}.jsonl"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel("DEBUG")  # always capture everything to file
    file_formatter = JsonFormatter()
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


# Singleton root logger for cross-module use
root_logger = get_logger("vhm")


def log_event(event_type: str, **kwargs) -> None:
    """
    Log a structured application event (DB error, ML training, alert trigger, etc.).

    Args:
        event_type: Short kebab-case slug e.g. "ml-training-start", "alert-fired"
        **kwargs: Arbitrary context key-value pairs attached to the log entry.
    """
    extra = {"event": event_type, **kwargs}
    root_logger.info(f"Event: {event_type}", extra={"extra": extra})
