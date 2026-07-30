"""Client operations against recorded fixtures (respx-mocked httpx)."""

from __future__ import annotations

import datetime
import json
from typing import Any

import httpx
import pytest
import respx

from senscritique import (
    CollectionAction,
    ParseError,
    RateLimit,
    RetryConfig,
    SensCritique,
    Universe,
    UserNotFoundError,
)
from senscritique._transport import GRAPHQL_URL, AsyncTransport


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
async def test_list_details(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("list_details.json"))
    async with make_client() as sc:
        details = await sc.list_details(
            "https://www.senscritique.com/liste/some_list/54812"
        )
    assert details.id == 54812
    assert details.universe_id == 1
    assert details.is_ordered is True
    assert details.is_official is False
    assert details.product_count == 111
    assert details.author_username == "MilOvni"


@respx.mock
async def test_list_details_unknown_id() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"userList": None}})
    async with make_client() as sc:
        with pytest.raises(ParseError, match="unknown id"):
            await sc.list_details(999999999)


@respx.mock
async def test_list_items_paginates(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("list_items_page1.json")),
        httpx.Response(200, json=load_fixture("list_items_page2.json")),
    ]
    async with make_client() as sc:
        items = [item async for item in sc.list_items(54812, page_size=2)]
    assert [i.position for i in items] == [1, 2, 3]
    assert items[0].work.id == 494050
    assert items[0].annotation is not None
    assert graphql_variables(route.calls[1].request)["offset"] == 2


@respx.mock
async def test_search_lists(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("list_search.json"))
    async with make_client() as sc:
        hits = await sc.search_lists("science fiction", limit=2)
    assert hits[0].id == 54812
    assert hits[0].like_count == 442
    assert hits[0].universe_id == 1
    assert hits[0].product_count == 111
    assert hits[0].author_username == "MilOvni"


@respx.mock
async def test_top10_list(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("top10_list.json"))
    async with make_client() as sc:
        details = await sc.top10_list("movie")
    assert details.id == 180
    assert details.label == "Top 100 films des Tops 10"
    assert details.author_username == "senscritique"
    assert graphql_variables(route.calls[0].request)["universe"] == "movie"


@respx.mock
async def test_poll_details(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("poll_details.json"))
    async with make_client() as sc:
        poll = await sc.poll(2582684)
    assert poll.id == 2582684
    assert poll.label == "Les meilleures séries de 2020"
    assert poll.universe_id == 4
    assert poll.participation_count is not None


@respx.mock
async def test_poll_works(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("poll_works.json"))
    async with make_client() as sc:
        result = await sc.poll_works_all(2582684)
    # One short page (3 < default page size) stops the iteration.
    assert len(route.calls) == 1
    assert [w.id for w in result.items] == [39032081, 39579996, 35141553]
    assert result.ok


@respx.mock
async def test_polls_universe_variable(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("polls.json"))
    async with make_client() as sc:
        polls = await sc.polls("movie", limit=3)
    assert polls[0].id == 4238470
    assert polls[0].universe_id == 1
    assert graphql_variables(route.calls[0].request)["universe"] == "movie"


@respx.mock
async def test_top_polls(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("top_polls.json"))
    async with make_client() as sc:
        polls = await sc.top_polls()
    assert len(polls) == 2
    assert {p.universe_id for p in polls} == {4, 1}


@respx.mock
async def test_search_polls(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("poll_search.json"))
    async with make_client() as sc:
        hits = await sc.search_polls("2020", limit=3)
    assert hits[0].title == "Les meilleurs animes de 2020"
    # Poll search returns universe as the API string, kept raw.
    assert [h.universe for h in hits] == ["tvShow", "game", "musicAlbum"]
    assert hits[0].url is not None and hits[0].url.startswith("https://")


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


# -- browse and discovery ----------------------------------------------------


@respx.mock
async def test_genres(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("genres.json"))
    async with make_client() as sc:
        genres = await sc.genres("tvShow")
    # The fixture's last genre has no id and is skipped leniently.
    assert [g.id for g in genres] == [8673, 14717, 8775, 14713]
    assert genres[0].label == "Action"
    assert graphql_variables(route.calls[0].request)["universe"] == "tvShow"


@respx.mock
async def test_genres_strict_raises(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("genres.json"))
    async with make_client() as sc:
        with pytest.raises(ParseError):
            await sc.genres(strict=True)


@respx.mock
async def test_genre_products_paginates(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("genre_products_page1.json")),
        httpx.Response(200, json=load_fixture("genre_products_page2.json")),
    ]
    async with make_client() as sc:
        works = [
            work
            async for work in sc.genre_products(
                Universe.MOVIE, 8673, order="RATING_DESC", page_size=2
            )
        ]
    # Page 2's second product is malformed (no id) and is skipped leniently.
    assert [w.id for w in works] == [105117324, 41169272, 21636592]
    assert works[1].year is None
    variables = graphql_variables(route.calls[0].request)
    assert variables["genre"] == 8673
    assert variables["order"] == "RATING_DESC"
    assert variables["universe"] == "movie"
    assert graphql_variables(route.calls[1].request)["offset"] == 2


@respx.mock
async def test_genre_products_strict_raises(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("genre_products_page1.json")),
        httpx.Response(200, json=load_fixture("genre_products_page2.json")),
    ]
    async with make_client() as sc:
        with pytest.raises(ParseError):
            await sc.genre_products_all(page_size=2, strict=True)


@respx.mock
async def test_genre_products_omits_unset_filters(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("genre_products_page1.json")),
        # An empty page ends the walk even when the total says otherwise.
        httpx.Response(
            200, json={"data": {"genreProducts": {"total": 3, "products": []}}}
        ),
    ]
    async with make_client() as sc:
        result = await sc.genre_products_all(page_size=2)
    assert len(result.items) == 2
    assert len(route.calls) == 2
    variables = graphql_variables(route.calls[0].request)
    assert "genre" not in variables
    assert "order" not in variables


@respx.mock
async def test_products_by_release(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("products_by_release.json"))
    async with make_client() as sc:
        result = await sc.products_by_release_all(
            year=2025, sort_by="RATING", page_size=3
        )
    assert len(route.calls) == 1
    assert [w.year for w in result.items] == [2025, 2025, 2025]
    variables = graphql_variables(route.calls[0].request)
    # A year filter only applies alongside byPeriod/period.
    assert variables["year"] == 2025
    assert variables["byPeriod"] is True
    assert variables["period"] == "OUTBYYEAR"
    assert variables["sortBy"] == "RATING"


@respx.mock
async def test_products_by_release_without_year(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("products_by_release.json"))
    async with make_client() as sc:
        works = [
            work
            async for work in sc.products_by_release("book", page_size=3)
        ]
    assert len(works) == 3
    variables = graphql_variables(route.calls[0].request)
    assert variables["universe"] == "book"
    assert "year" not in variables
    assert "byPeriod" not in variables


@respx.mock
async def test_products_by_month_stops_on_short_page(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("products_by_month.json"))
    async with make_client() as sc:
        works = [
            work async for work in sc.products_by_month(2026, 6, page_size=5)
        ]
    # The bare product list carries no total: a short page ends the walk.
    assert len(route.calls) == 1
    assert len(works) == 3
    variables = graphql_variables(route.calls[0].request)
    assert variables["year"] == 2026
    assert variables["month"] == 6


@respx.mock
async def test_release_listings_mirror_iterator_and_collector(
    load_fixture: Any,
) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("products_by_month.json")),
        httpx.Response(200, json=load_fixture("products_by_day.json")),
    ]
    async with make_client() as sc:
        month = await sc.products_by_month_all(2026, 6, "tvShow", page_size=5)
        week = [
            work async for work in sc.products_by_day(2026, 6, 3, page_size=5)
        ]
    assert len(month.items) == 3
    assert len(week) == 3
    assert graphql_variables(route.calls[0].request)["universe"] == "tvShow"


@respx.mock
async def test_products_by_day(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("products_by_day.json"))
    async with make_client() as sc:
        result = await sc.products_by_day_all(2026, 6, 3, page_size=5)
    assert [w.id for w in result.items] == [71656739, 133857629, 130626731]
    assert result.ok
    assert graphql_variables(route.calls[0].request)["day"] == 3


@respx.mock
async def test_group_products_skips_unmapped_universes(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("group_products.json"))
    async with make_client() as sc:
        # No total on this listing: a page shorter than page_size ends it.
        result = await sc.group_products_all(260, page_size=5)
    assert len(route.calls) == 1
    # The Dune franchise spans universes; the game (3) and album (7) entries
    # are unmapped and reported as skipped items.
    assert [w.id for w in result.items] == [73299785]
    assert len(result.errors) == 2
    assert result.ok is False
    variables = graphql_variables(route.calls[0].request)
    assert variables["franchiseId"] == 260
    assert "universe" not in variables


@respx.mock
async def test_group_products_strict_raises(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("group_products.json"))
    async with make_client() as sc:
        with pytest.raises(ParseError):
            _ = [
                work
                async for work in sc.group_products(
                    260, Universe.MOVIE, order="DATE_RELEASE_DESC", strict=True
                )
            ]
    variables = graphql_variables(route.calls[0].request)
    assert variables["universe"] == "movie"
    assert variables["order"] == "DATE_RELEASE_DESC"


@respx.mock
async def test_group_products_walks_full_pages(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("group_products.json")),
        httpx.Response(200, json={"data": {"groupProducts": {"items": []}}}),
    ]
    async with make_client() as sc:
        works = [
            work async for work in sc.group_products(260, page_size=3)
        ]
    # A full page asks for the next one; the empty page ends the walk.
    assert len(route.calls) == 2
    assert [w.id for w in works] == [73299785]
    assert graphql_variables(route.calls[1].request)["offset"] == 3


@respx.mock
async def test_providers(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("providers.json"))
    async with make_client() as sc:
        providers = await sc.providers()
    # The fixture's last provider has no name and is skipped leniently.
    assert [(p.id, p.name) for p in providers] == [
        (1, "Netflix"),
        (2, "Prime Video"),
        (3, "OCS"),
        (4, "Canal+"),
    ]


@respx.mock
async def test_providers_strict_raises(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("providers.json"))
    async with make_client() as sc:
        with pytest.raises(ParseError):
            await sc.providers(strict=True)


@respx.mock
async def test_streaming_explorer(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("streaming_explorer.json"))
    async with make_client() as sc:
        works = [
            work
            async for work in sc.streaming_explorer(
                provider_ids=[1],
                genre_ids=[8673],
                years=[1990, 2000],
                ratings=[7, 10],
                only_popular=True,
                order="RATING_DESC",
                page_size=3,
            )
        ]
    assert len(works) == 3
    assert works[0].universe is Universe.MOVIE
    variables = graphql_variables(route.calls[0].request)
    # The API calls the universe "subtype" here.
    assert variables["subtype"] == "movie"
    assert variables["providers"] == [1]
    assert variables["genres"] == [8673]
    assert variables["yearDateRelease"] == [1990, 2000]
    assert variables["rating"] == [7, 10]
    assert variables["onlyPopular"] is True
    assert variables["order"] == "RATING_DESC"


@respx.mock
async def test_streaming_explorer_all(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("streaming_explorer.json"))
    async with make_client() as sc:
        result = await sc.streaming_explorer_all("tvShow", page_size=3)
    assert result.ok
    assert len(result.items) == 3
    variables = graphql_variables(route.calls[0].request)
    assert variables["subtype"] == "tvShow"
    assert "providers" not in variables


@respx.mock
async def test_discover_products(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("discover_products.json"))
    async with make_client() as sc:
        discovery = await sc.discover_products(
            mood="GOOD_VIBES", type="BANGER", excluded_ids=[1, 2]
        )
    assert discovery.fresh is not None
    assert discovery.fresh.work.id == 133849382
    assert discovery.fresh.similar is None
    assert discovery.popular is not None
    assert discovery.popular.work.title == "Kill Bill - Volume 1"
    variables = graphql_variables(route.calls[0].request)
    assert variables["mood"] == "GOOD_VIBES"
    assert variables["type"] == "BANGER"
    assert variables["excludedProductIds"] == [1, 2]


@respx.mock
async def test_discover_products_missing_payload() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"discoverProducts": None}})
    async with make_client() as sc:
        with pytest.raises(ParseError):
            await sc.discover_products()


# -- people ------------------------------------------------------------------


@respx.mock
async def test_contact(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("contact.json"))
    async with make_client() as sc:
        contact = await sc.contact("/contact/steven_spielberg/993")
    assert contact.id == 993
    assert contact.name == "Steven Spielberg"
    assert contact.professions == ("producers", "authors", "developers")
    assert contact.nationalities == ("Américain",)
    assert contact.countries == ("United States of America",)
    # The API returns Paris midnight as a UTC instant; the date is the 18th.
    assert contact.date_of_birth == datetime.date(1946, 12, 18)
    assert contact.date_of_death is None
    assert contact.place_of_birth == "Cincinnati"
    assert contact.product_count == 307
    # Zero-count universes are dropped.
    assert contact.product_counts == {
        "movie": 215,
        "book": 2,
        "game": 2,
        "tvShow": 40,
    }
    assert [w.id for w in contact.best_products] == [117662, 43486292, 422876]
    assert graphql_variables(route.calls[0].request)["id"] == 993


@respx.mock
async def test_contact_unknown_id() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"contact": None}})
    async with make_client() as sc:
        with pytest.raises(ParseError, match="unknown id"):
            await sc.contact(999999999)


@respx.mock
async def test_contact_products_paginates(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("contact_products_page1.json")),
        httpx.Response(200, json=load_fixture("contact_products_page2.json")),
    ]
    async with make_client() as sc:
        works = [
            work
            async for work in sc.contact_products(
                993,
                Universe.MOVIE,
                profession="directors",
                order="RATING_DESC",
                page_size=2,
            )
        ]
    # Page 2's second product is malformed (no title) and is skipped.
    assert [w.id for w in works] == [43486292, 422876, 400170]
    variables = graphql_variables(route.calls[0].request)
    assert variables["universe"] == "movie"
    assert variables["profession"] == "directors"
    assert variables["order"] == "RATING_DESC"
    assert graphql_variables(route.calls[1].request)["offset"] == 2


@respx.mock
async def test_contact_products_strict_raises(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("contact_products_page1.json")),
        httpx.Response(200, json=load_fixture("contact_products_page2.json")),
    ]
    async with make_client() as sc:
        with pytest.raises(ParseError):
            await sc.contact_products_all(993, page_size=2, strict=True)


@respx.mock
async def test_contact_products_unknown_id() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"contact": None}})
    async with make_client() as sc:
        with pytest.raises(ParseError, match="unknown id"):
            await sc.contact_products_all(999999999)


@respx.mock
async def test_search_contacts(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.respond(json=load_fixture("contact_search.json"))
    async with make_client() as sc:
        hits = await sc.search_contacts("murnau", limit=3)
    # The fixture's last hit has no name and is skipped leniently.
    assert [h.id for h in hits] == [6618669, 942, 4793802]
    assert hits[1].name == "Friedrich Wilhelm Murnau"
    assert hits[1].professions == ("directors",)
    assert hits[1].picture_url is not None
    assert graphql_variables(route.calls[0].request)["query"] == "murnau"


@respx.mock
async def test_search_contacts_strict_raises(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("contact_search.json"))
    async with make_client() as sc:
        with pytest.raises(ParseError):
            await sc.search_contacts("murnau", strict=True)
