"""Structured logging configuration for the service."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_STANDARD_RECORD_FIELDS = frozenset(
    {
        *logging.makeLogRecord({}).__dict__,
        "asctime",
        "message",
    }
)


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _STANDARD_RECORD_FIELDS
            }
        )
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Configure the root logger to write structured JSON to stdout."""
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(resolved_level)
