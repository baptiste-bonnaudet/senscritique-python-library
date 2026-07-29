"""Shared unit-test fixtures."""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture() -> Any:
    def _load(name: str) -> Any:
        return json.loads((FIXTURES / name).read_text())

    return _load
