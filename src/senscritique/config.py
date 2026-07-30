"""Library configuration sourced from environment variables."""

from __future__ import annotations

import logging
import os

_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _resolve_log_level() -> int:
    raw = os.getenv("SENSCRITIQUE_LOG_LEVEL") or os.getenv("LOG_LEVEL") or "INFO"
    return _LOG_LEVELS.get(raw.upper(), logging.INFO)


LOG_LEVEL: int = _resolve_log_level()
