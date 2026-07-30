"""Parser edge cases: nulls, malformed payloads, id extraction."""

from __future__ import annotations

import datetime

import pytest

from senscritique import CollectionAction, ParseError, Universe
from senscritique._parse import (
    coerce_universe,
    extract_numeric_id,
    parse_collection_item,
    parse_contact_details,
    parse_contact_search_hit,
    parse_date,
    parse_datetime,
    parse_discovery,
    parse_genre,
    parse_paris_date,
    parse_review,
    parse_streaming_provider,
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


def test_parse_paris_date_shifts_back_to_the_calendar_day() -> None:
    # The API stores birthdays as Paris midnight expressed in UTC.
    assert parse_paris_date("1946-12-17T23:00:00.000Z") == datetime.date(
        1946, 12, 18
    )
    assert parse_paris_date("1927-07-05T00:00:00.000Z") == datetime.date(1927, 7, 5)
    assert parse_paris_date(None) is None
    with pytest.raises(ParseError):
        parse_paris_date("not a date")


def test_parse_genre_and_provider_reject_bad_payloads() -> None:
    assert parse_genre({"id": 8673, "label": None}).label is None
    with pytest.raises(ParseError, match="invalid genre"):
        parse_genre({"label": "Action"})
    with pytest.raises(ParseError, match="invalid provider"):
        parse_streaming_provider({"id": 1})


def test_parse_contact_details_minimal() -> None:
    contact = parse_contact_details({"id": 1, "name": "X"})
    assert contact.professions == ()
    assert contact.nationalities == ()
    assert contact.date_of_birth is None
    assert contact.product_counts == {}
    assert contact.best_products == ()
    with pytest.raises(ParseError, match="invalid contact details"):
        parse_contact_details({"id": 1})


def test_parse_contact_details_drops_unmapped_best_products() -> None:
    contact = parse_contact_details(
        {
            "id": 1,
            "name": "X",
            "profession": ["directors", None, ""],
            "bestProducts": [
                {"id": 2, "title": "A movie", "universe": 1},
                {"id": 3, "title": "An album", "universe": 7},
            ],
        }
    )
    assert contact.professions == ("directors",)
    assert [w.id for w in contact.best_products] == [2]


def test_parse_contact_search_hit_requires_a_name() -> None:
    with pytest.raises(ParseError, match="invalid contact search"):
        parse_contact_search_hit({"id": 1, "url": "/contact/x/1"})


def test_parse_discovery_keeps_similar_and_tolerates_gaps() -> None:
    discovery = parse_discovery(
        {
            "freshProduct": {
                "product": {"id": 1, "title": "Fresh", "universe": 1},
                "similarProduct": {"id": 2, "title": "Similar", "universe": 1},
            },
            "popularProduct": {
                "product": {"id": 3, "title": "Popular", "universe": 1},
                # An unmapped-universe suggestion must not kill the pick.
                "similarProduct": {"id": 4, "title": "Album", "universe": 7},
            },
        }
    )
    assert discovery.fresh is not None
    assert discovery.fresh.similar is not None
    assert discovery.fresh.similar.id == 2
    assert discovery.popular is not None
    assert discovery.popular.similar is None


def test_parse_discovery_empty_slots() -> None:
    discovery = parse_discovery({"freshProduct": None, "popularProduct": {}})
    assert discovery.fresh is None
    assert discovery.popular is None
