"""Unit tests for logger construction."""

import logging

from senscritique.logger import build_logger


def test_build_logger_returns_configured_logger() -> None:
    logger = build_logger("test-logger")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test-logger"
    assert logger.handlers, "expected at least one handler to be attached"


def test_build_logger_does_not_duplicate_handlers() -> None:
    first = build_logger("test-logger-dedup")
    second = build_logger("test-logger-dedup")

    assert first is second
    assert len(second.handlers) == 1
