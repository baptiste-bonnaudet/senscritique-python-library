"""Unit tests for the config helpers."""

import importlib
import logging

import pytest


def test_log_level_defaults_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENSCRITIQUE_LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    from senscritique import config

    reloaded = importlib.reload(config)
    assert reloaded.LOG_LEVEL == logging.INFO


def test_log_level_prefers_scoped_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSCRITIQUE_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    from senscritique import config

    reloaded = importlib.reload(config)
    assert reloaded.LOG_LEVEL == logging.ERROR


def test_log_level_ignores_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSCRITIQUE_LOG_LEVEL", "nonsense")
    from senscritique import config

    reloaded = importlib.reload(config)
    assert reloaded.LOG_LEVEL == logging.INFO
