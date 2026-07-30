"""Sync facade: same operations, blocking API, private loop thread."""

from __future__ import annotations

from typing import Any

import httpx
import respx

from senscritique import RateLimit, RetryConfig, SensCritiqueSync, Universe
from senscritique._transport import GRAPHQL_URL


def make_sync_client() -> SensCritiqueSync:
    return SensCritiqueSync(
        rate_limit=RateLimit(min_interval=0), retry=RetryConfig(max_retries=0)
    )


@respx.mock
def test_sync_search(load_fixture: Any) -> None:
    respx.post(GRAPHQL_URL).respond(json=load_fixture("search.json"))
    with make_sync_client() as sc:
        results = sc.search("dune", universe=Universe.MOVIE)
    assert results[0].display_title == "Dune: Part Two"


@respx.mock
def test_sync_collection_iterator(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("collection_page1.json")),
        httpx.Response(200, json=load_fixture("collection_page2.json")),
    ]
    with make_sync_client() as sc:
        items = list(sc.collection("vsv", page_size=2))
    assert len(items) == 2
    assert items[0].work.title == "Mercuriales"


@respx.mock
def test_sync_collection_all(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("collection_page1.json")),
        httpx.Response(200, json=load_fixture("collection_page2.json")),
    ]
    with make_sync_client() as sc:
        result = sc.collection_all("vsv", page_size=2)
    assert len(result.items) == 2
    assert len(result.errors) == 1


@respx.mock
def test_sync_work_details_and_review(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("work_details.json")),
        httpx.Response(200, json=load_fixture("review.json")),
    ]
    with make_sync_client() as sc:
        details = sc.work_details(451178)
        review = sc.review(7355694)
    assert details.title == "L'Aurore"
    assert review.rating == 10


@respx.mock
def test_sync_browse_and_people(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("genres.json")),
        httpx.Response(200, json=load_fixture("providers.json")),
        httpx.Response(200, json=load_fixture("discover_products.json")),
        httpx.Response(200, json=load_fixture("contact.json")),
        httpx.Response(200, json=load_fixture("contact_search.json")),
        httpx.Response(200, json=load_fixture("products_by_month.json")),
    ]
    with make_sync_client() as sc:
        genres = sc.genres(Universe.TV_SHOW)
        providers = sc.providers()
        discovery = sc.discover_products()
        contact = sc.contact(993)
        hits = sc.search_contacts("murnau")
        releases = list(sc.products_by_month(2026, 6, page_size=5))
    assert genres[0].label == "Action"
    assert providers[0].name == "Netflix"
    assert discovery.popular is not None
    assert contact.name == "Steven Spielberg"
    assert hits[0].name == "F.W. Murnau"
    assert len(releases) == 3


@respx.mock
def test_sync_contact_products_iterator(load_fixture: Any) -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(200, json=load_fixture("contact_products_page1.json")),
        httpx.Response(200, json=load_fixture("contact_products_page2.json")),
    ]
    with make_sync_client() as sc:
        works = list(sc.contact_products(993, "movie", page_size=2))
    assert [w.id for w in works] == [43486292, 422876, 400170]


def test_sync_close_is_idempotent() -> None:
    sc = make_sync_client()
    sc.close()
    sc.close()
