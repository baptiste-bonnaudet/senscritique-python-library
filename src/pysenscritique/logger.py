"""Structured JSON logging setup."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from sys import stdout
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from .config import LOG_LEVEL


class CustomJsonFormatter(JsonFormatter):
    """JSON formatter that adds an ISO-8601 timestamp and a normalized level."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            log_record["timestamp"] = datetime.now(UTC).isoformat()
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def build_logger(name: str) -> logging.Logger:
    """Return a configured logger named ``name``."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    if not logger.handlers:
        handler = logging.StreamHandler(stdout)
        handler.setFormatter(
            CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
        )
        handler.setLevel(LOG_LEVEL)
        logger.addHandler(handler)
    return logger
