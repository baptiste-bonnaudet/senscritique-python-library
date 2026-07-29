"""Client operations against recorded fixtures (respx-mocked httpx)."""

from __future__ import annotations

import datetime
import json
from typing import Any

import httpx
import pytest
import respx

from pysenscritique import (
    CollectionAction,
    ParseError,
    RateLimit,
    RetryConfig,
    SensCritique,
    Universe,
    UserNotFoundError,
)
from pysenscritique._transport import GRAPHQL_URL, AsyncTransport


def make_client() -> SensCritique:
    return SensCritique(
        transport=AsyncTransport(
            rate_limit=RateLimit(min_interval=0),
            retry=RetryConfig(max_retries=0),
        )
    )


def graphql_variables(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content)["variables"]  # type: ignore[no-any-return]


@respx.mock
async def test_collection_paginates(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("collection_page1.json")),
        httpx.Response(200, json=load_fixture("collection_page2.json")),
    ]
    async with make_client() as sc:
        items = [item async for item in sc.collection("vsv", page_size=2)]

    # Page 2's only item is malformed (no id) and is skipped leniently.
    assert len(items) == 2
    first, second = items
    assert first.work.id == 11348008
    assert first.user_rating == 8
    assert first.date_done == datetime.date(2021, 3, 14)
    assert first.is_reviewed is True
    assert first.review_url == "/film/mercuriales/critique/123456"
    assert second.user_rating is None
    assert second.date_done is None
    assert second.work.year is None

    # Both pages requested, offset advanced by page length.
    assert graphql_variables(route.calls[0].request)["offset"] == 0
    assert graphql_variables(route.calls[1].request)["offset"] == 2
    assert graphql_variables(route.calls[0].request)["universe"] == "movie"
    assert graphql_variables(route.calls[0].request)["action"] == "DONE"


@respx.mock
async def test_collection_strict_raises(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("collection_page1.json")),
        httpx.Response(200, json=load_fixture("collection_page2.json")),
    ]
    async with make_client() as sc:
        with pytest.raises(ParseError):
            _ = [
                item
                async for item in sc.collection("vsv", strict=True, page_size=2)
            ]


@respx.mock
async def test_collection_all_reports_errors(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("collection_page1.json")),
        httpx.Response(200, json=load_fixture("collection_page2.json")),
    ]
    async with make_client() as sc:
        result = await sc.collection_all(
            "vsv", Universe.MOVIE, CollectionAction.DONE, page_size=2
        )
    assert len(result.items) == 2
    assert len(result.errors) == 1
    assert not result.ok
    assert result.errors[0].error_type == "ParseError"
    assert "id" in result.errors[0].message


@respx.mock
async def test_collection_unknown_user(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("user_not_found.json"))
    async with make_client() as sc:
        with pytest.raises(UserNotFoundError, match="ghost_user_42"):
            _ = [item async for item in sc.collection("ghost_user_42")]


@respx.mock
async def test_collection_empty() -> None:
    respx.post(GRAPHQL_URL).respond(
        json={"data": {"user": {"collection": {"total": 0, "products": None}}}}
    )
    async with make_client() as sc:
        items = [item async for item in sc.collection("vsv", Universe.BOOK)]
    assert items == []


@respx.mock
async def test_search(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("search.json"))
    async with make_client() as sc:
        results = await sc.search("dune", universe="movie", limit=5)
    assert [w.display_title for w in results] == [
        "Dune: Part Two",
        "Dune",
        "Dune",
    ]
    assert all(w.universe is Universe.MOVIE for w in results)
    variables = graphql_variables(route.calls[0].request)
    assert variables["filters"] == [
        {"identifier": "universe", "termValues": ["movie"]}
    ]


@respx.mock
async def test_search_without_universe(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("search.json"))
    async with make_client() as sc:
        await sc.search("dune")
    assert graphql_variables(route.calls[0].request)["filters"] == []


@respx.mock
async def test_work_details(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("work_details.json"))
    async with make_client() as sc:
        details = await sc.work_details(
            "https://www.senscritique.com/film/l_aurore/451178"
        )
    assert details.id == 451178
    assert details.original_title == "Sunrise: A Song of Two Humans"
    assert details.year == 1928
    assert details.universe is Universe.MOVIE
    assert details.creators == ("Friedrich Wilhelm Murnau",)
    assert details.genres == ("Drame", "Romance", "Muet")
    assert details.duration_seconds == 5640
    assert details.release_date == datetime.date(1927, 11, 4)
    assert details.rating_count == 9182
    assert details.picture_url is not None


@respx.mock
async def test_work_details_unknown_id() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"product": None}})
    async with make_client() as sc:
        with pytest.raises(ParseError, match="unknown id"):
            await sc.work_details(999999999)


@respx.mock
async def test_topchart(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("topchart.json"))
    async with make_client() as sc:
        entries = await sc.topchart("movie", limit=3)
    assert [e.position for e in entries] == [1, 2, 3]
    assert entries[0].work.display_title == "12 Angry Men"
    variables = graphql_variables(route.calls[0].request)
    assert variables["subtype"] == "TOP_111"
    assert variables["universe"] == "movie"


@respx.mock
async def test_review(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("review.json"))
    async with make_client() as sc:
        review = await sc.review("/film/l_aurore/critique/7355694")
    assert review.id == 7355694
    assert review.title == "Amour et Désir"
    assert review.rating == 10
    assert review.author_username == "Aurea"
    assert review.body_html is not None
    assert review.body_html.startswith("<p>")
    assert review.date_created is not None
    assert review.date_created.year == 2022


@respx.mock
async def test_review_unknown_id() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"review": None}})
    async with make_client() as sc:
        with pytest.raises(ParseError, match="unknown id"):
            await sc.review(1)


async def test_invalid_action_rejected() -> None:
    async with make_client() as sc:
        with pytest.raises(ValueError):
            _ = [item async for item in sc.collection("vsv", action="RATED")]
