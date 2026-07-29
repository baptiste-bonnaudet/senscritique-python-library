"""Model behavior: universes, null handling, bulk results."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pysenscritique import BulkError, BulkResult, Universe, WorkSummary


def test_universe_api_strings() -> None:
    assert Universe.MOVIE.value == "movie"
    assert Universe.TV_SHOW.value == "tvShow"
    assert Universe.BOOK.value == "book"


def test_universe_numeric_ids() -> None:
    assert Universe.MOVIE.numeric_id == 1
    assert Universe.BOOK.numeric_id == 2
    assert Universe.TV_SHOW.numeric_id == 4


def test_work_summary_nulls_stay_none() -> None:
    work = WorkSummary(id=1, title="X", universe=Universe.MOVIE)
    assert work.year is None
    assert work.rating is None
    assert work.original_title is None
    assert "None" not in work.display_title


def test_display_title_prefers_original() -> None:
    work = WorkSummary(
        id=1, title="L'Aurore", original_title="Sunrise", universe=Universe.MOVIE
    )
    assert work.display_title == "Sunrise"
    untranslated = WorkSummary(id=2, title="Mercuriales", universe=Universe.MOVIE)
    assert untranslated.display_title == "Mercuriales"


def test_work_summary_rejects_bad_payload() -> None:
    with pytest.raises(ValidationError):
        WorkSummary(id="not-an-int", title="X", universe=Universe.MOVIE)  # type: ignore[arg-type]


def test_bulk_result_ok() -> None:
    good: BulkResult[int] = BulkResult(items=[1, 2], errors=[])
    assert good.ok
    bad: BulkResult[int] = BulkResult(
        items=[1],
        errors=[BulkError(payload={}, error_type="ParseError", message="boom")],
    )
    assert not bad.ok
