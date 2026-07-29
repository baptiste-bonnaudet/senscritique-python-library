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
async def test_collection_filter_variables(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("collection_page2.json"))
    async with make_client() as sc:
        await sc.collection_all(
            "vsv",
            action="RATING",
            year_date_done=2021,
            order="USER_RATING_DESC",
            keywords="dune",
        )
    variables = graphql_variables(route.calls[0].request)
    assert variables["action"] == "RATING"
    assert variables["yearDateDone"] == 2021
    assert variables["order"] == "USER_RATING_DESC"
    assert variables["keywords"] == "dune"
    assert "genreId" not in variables
    assert "isAgenda" not in variables


async def test_collection_invalid_sort_rejected() -> None:
    async with make_client() as sc:
        with pytest.raises(ValueError):
            await sc.collection_all("vsv", order="BEST_FIRST")


@respx.mock
async def test_user_profile(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("user_profile.json"))
    async with make_client() as sc:
        profile = await sc.user_profile("vsv")
    assert profile.id == 200295
    assert profile.username == "vsv"
    assert profile.date_created is not None
    assert profile.date_created.year == 2014
    assert profile.avatar_url is not None
    assert profile.stats is not None
    assert profile.stats.collection_count == 1841
    assert profile.stats.diary_count == 348
    # Unmapped universes keep their API string keys; "total" is dropped.
    assert profile.rating_counts["movie"] == 947
    assert profile.rating_counts["musicAlbum"] == 554
    assert "total" not in profile.rating_counts
    assert profile.wish_counts["movie"] >= 0


@respx.mock
async def test_user_profile_unknown(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("user_not_found.json"))
    async with make_client() as sc:
        with pytest.raises(UserNotFoundError):
            await sc.user_profile("ghost_user_42")


@respx.mock
async def test_search_users(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("user_search.json"))
    async with make_client() as sc:
        hits = await sc.search_users("sergent", limit=3)
    # The id-less hit is skipped leniently.
    assert [h.username for h in hits] == ["Sergent_Pepper", "Sergent-Steiner"]
    assert hits[0].id == 105078
    assert hits[0].followers_count == 17502
    assert hits[0].rating_count == 11289
    assert hits[0].url == "https://www.senscritique.com/Sergent_Pepper"
    variables = graphql_variables(route.calls[0].request)
    assert variables["query"] == "sergent"


@respx.mock
async def test_search_users_strict(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("user_search.json"))
    async with make_client() as sc:
        with pytest.raises(ParseError):
            await sc.search_users("sergent", strict=True)


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
async def test_autocomplete(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("autocomplete.json"))
    async with make_client() as sc:
        hits = await sc.autocomplete("spielberg", limit=6)
    # The unmapped-universe comic (universe 6) and the empty product/contact
    # item are both skipped leniently.
    assert len(hits) == 2
    person, film = hits
    assert person.work is None
    assert person.contact is not None
    assert person.contact.name == "Steven Spielberg"
    assert film.contact is None
    assert film.work is not None
    assert film.work.universe is Universe.MOVIE
    variables = graphql_variables(route.calls[0].request)
    assert variables["keywords"] == "spielberg"
    assert "universe" not in variables


@respx.mock
async def test_autocomplete_strict_raises(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("autocomplete.json"))
    async with make_client() as sc:
        with pytest.raises(ParseError, match="unknown universe"):
            await sc.autocomplete("spielberg", strict=True)


@respx.mock
async def test_autocomplete_universe_filter(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("autocomplete.json"))
    async with make_client() as sc:
        await sc.autocomplete("spielberg", universe="movie")
    assert graphql_variables(route.calls[0].request)["universe"] == "movie"


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
async def test_work_details_full(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("work_details_full.json"))
    async with make_client() as sc:
        details = await sc.work_details(45424060)
    assert details.title == "Dune - Deuxième partie"
    assert details.alternative_titles == ("Dune 2",)
    assert details.screenwriters == ("Denis Villeneuve", "Jon Spaihts")
    assert details.producers == ("Denis Villeneuve", "Thomas Tull")
    assert [c.name for c in details.cast] == [
        "Timothée Chalamet",
        "Zendaya",
        "Rebecca Ferguson",
    ]
    assert details.cast[0].role == "Paul Atreides"
    assert details.cast[0].person_id == 1248505
    assert details.stats is not None
    assert details.stats.wish_count == 5182
    assert details.rating_histogram is not None
    assert details.rating_histogram.count_for(8) == 12533
    assert details.rating_histogram.total == 36625
    assert details.providers[0].name == "MAX"
    assert details.providers[0].provider_id == 28
    offers = details.vod_offers
    assert {o.platform for o in offers} == {"VIVA"}
    assert {o.mode for o in offers} == {"TVOD", "VODEST"}
    assert offers[0].price == 2.99
    assert details.franchises[0].label == "Dune"
    assert details.number_of_seasons is None
    assert details.seasons == ()
    assert details.backdrop_url is not None


@respx.mock
async def test_work_details_show_seasons(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("work_details_show.json"))
    async with make_client() as sc:
        details = await sc.work_details(264963)
    assert details.universe is Universe.TV_SHOW
    assert details.number_of_seasons == 5
    assert [s.title for s in details.seasons] == [
        "Breaking Bad - Saison 1",
        "Breaking Bad - Saison 2",
    ]
    assert details.seasons[0].url == "/serie/breaking_bad/264963/S1"
    assert details.seasons[0].rating == 8.1
    assert details.creators == ("Vince Gilligan",)


@respx.mock
async def test_work_reviews_paginates(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("work_reviews_page1.json")),
        httpx.Response(200, json=load_fixture("work_reviews_page2.json")),
    ]
    async with make_client() as sc:
        reviews = [
            r async for r in sc.work_reviews(45424060, page_size=2, sort_by="DATE_DESC")
        ]
    assert [r.id for r in reviews] == [278545164, 302330727, 301955219]
    assert reviews[0].author_username == "Sergent_Pepper"
    assert reviews[0].rating == 9
    variables = graphql_variables(route.calls[0].request)
    assert variables["limit"] == 2
    assert variables["offset"] == 0
    assert variables["sortBy"] == "DATE_DESC"
    assert graphql_variables(route.calls[1].request)["offset"] == 2


@respx.mock
async def test_work_reviews_filter_variables(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("work_reviews_page2.json"))
    async with make_client() as sc:
        await sc.work_reviews_all(45424060, filter="POSITIVE")
    variables = graphql_variables(route.calls[0].request)
    assert variables["filter"] == "POSITIVE"
    assert "sortBy" not in variables


@respx.mock
async def test_work_shouts_lenient_and_all(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("work_shouts.json"))
    async with make_client() as sc:
        result = await sc.work_shouts_all(45424060)
    # The id-less shout is reported, not raised.
    assert [s.id for s in result.items] == [397332, 504753]
    assert len(result.errors) == 1
    assert result.items[0].like_count == 109
    assert result.items[0].author_username == "mikeopuvty"
    assert result.items[0].date_created is not None
    assert result.items[0].rating is None


@respx.mock
async def test_work_shouts_strict(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("work_shouts.json"))
    async with make_client() as sc:
        with pytest.raises(ParseError):
            _ = [s async for s in sc.work_shouts(45424060, strict=True)]


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
