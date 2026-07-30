"""Parser edge cases: nulls, malformed payloads, id extraction."""

from __future__ import annotations

import datetime

import pytest

from senscritique import CollectionAction, ParseError, Universe
from senscritique._parse import (
    coerce_universe,
    extract_numeric_id,
    parse_collection_item,
    parse_date,
    parse_datetime,
    parse_review,
    parse_work_details,
    parse_work_summary,
    universe_from_number,
)


def test_universe_from_number() -> None:
    assert universe_from_number(1) is Universe.MOVIE
    assert universe_from_number(2) is Universe.BOOK
    assert universe_from_number(4) is Universe.TV_SHOW
    with pytest.raises(ParseError):
        universe_from_number(99)
    with pytest.raises(ParseError):
        universe_from_number(None)


def test_coerce_universe() -> None:
    assert coerce_universe("movie") is Universe.MOVIE
    assert coerce_universe("tvShow") is Universe.TV_SHOW
    assert coerce_universe(Universe.BOOK) is Universe.BOOK
    with pytest.raises(ValueError, match="invalid universe"):
        coerce_universe("films")


def test_parse_date() -> None:
    assert parse_date(None) is None
    assert parse_date("2021-03-14T00:00:00Z") == datetime.date(2021, 3, 14)
    assert parse_date("1927-11-04") == datetime.date(1927, 11, 4)
    with pytest.raises(ParseError):
        parse_date("not a date")


def test_parse_datetime() -> None:
    assert parse_datetime(None) is None
    parsed = parse_datetime("2022-05-05T16:10:33.000Z")
    assert parsed == datetime.datetime(
        2022, 5, 5, 16, 10, 33, tzinfo=datetime.UTC
    )
    with pytest.raises(ParseError):
        parse_datetime(1234)


def test_parse_work_summary_null_fields() -> None:
    work = parse_work_summary(
        {"id": 5, "title": "X", "yearOfProduction": None, "universe": 1}
    )
    assert work.year is None
    assert work.rating is None


def test_parse_work_summary_missing_id() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_work_summary({"title": "X", "universe": 1})
    assert excinfo.value.payload is not None


def test_parse_collection_item_null_infos() -> None:
    item = parse_collection_item(
        {"id": 5, "title": "X", "universe": 1, "otherUserInfos": None},
        CollectionAction.WISH,
    )
    assert item.action is CollectionAction.WISH
    assert item.user_rating is None
    assert item.date_done is None
    assert item.is_reviewed is False
    assert item.review_url is None


def test_parse_work_details_minimal() -> None:
    details = parse_work_details({"id": 7, "title": "X", "universe": 2})
    assert details.universe is Universe.BOOK
    assert details.genres == ()
    assert details.creators == ()
    assert details.release_date is None


def test_parse_review_minimal() -> None:
    review = parse_review({"id": 1, "url": "/film/x/critique/1"})
    assert review.title is None
    assert review.rating is None
    assert review.date_created is None


def test_extract_numeric_id() -> None:
    assert extract_numeric_id(451178, kind="work") == 451178
    assert extract_numeric_id("451178", kind="work") == 451178
    assert (
        extract_numeric_id(
            "https://www.senscritique.com/film/l_aurore/451178", kind="work"
        )
        == 451178
    )
    assert (
        extract_numeric_id("/film/l_aurore/critique/7355694/", kind="review")
        == 7355694
    )
    assert (
        extract_numeric_id(
            "https://www.senscritique.com/film/x/123?utm=y#frag", kind="work"
        )
        == 123
    )
    with pytest.raises(ValueError, match="cannot extract"):
        extract_numeric_id("https://www.senscritique.com/film/l_aurore", kind="work")
