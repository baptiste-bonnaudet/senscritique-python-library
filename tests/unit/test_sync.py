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


def test_sync_close_is_idempotent() -> None:
    sc = make_sync_client()
    sc.close()
    sc.close()
