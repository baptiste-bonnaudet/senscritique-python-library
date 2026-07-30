"""Live integration tests against the real SensCritique API.

Marked ``integration`` and skipped in default runs. Run manually with
``make test-integration``. Uses one small public account and the default
rate limiter, so the whole module stays polite (a few requests, spaced).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from senscritique import (
    CollectionAction,
    SensCritique,
    Universe,
    UserNotFoundError,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

# Public account with a mid-sized collection (also used by the s2l project).
USERNAME = "vsv"
# "L'Aurore" (Sunrise, 1927), a stable classic with plenty of reviews.
WORK_ID = 451178


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def client() -> AsyncIterator[SensCritique]:
    async with SensCritique() as sc:
        yield sc


async def test_collection_first_page(client: SensCritique) -> None:
    items = []
    async for item in client.collection(
        USERNAME, Universe.MOVIE, CollectionAction.DONE, page_size=5
    ):
        items.append(item)
        if len(items) >= 5:
            break
    assert len(items) == 5
    for item in items:
        assert item.work.id > 0
        assert item.work.title
        assert item.work.universe is Universe.MOVIE


async def test_unknown_user(client: SensCritique) -> None:
    with pytest.raises(UserNotFoundError):
        async for _ in client.collection("no_such_user_senscritique_x9"):
            pass


async def test_search(client: SensCritique) -> None:
    results = await client.search("dune", universe=Universe.MOVIE, limit=5)
    assert results
    assert any("Dune" in (w.display_title) for w in results)


async def test_work_details(client: SensCritique) -> None:
    details = await client.work_details(WORK_ID)
    assert details.original_title == "Sunrise: A Song of Two Humans"
    assert details.year == 1928
    assert details.creators


async def test_topchart(client: SensCritique) -> None:
    entries = await client.topchart(Universe.MOVIE, limit=5)
    assert len(entries) == 5
    assert entries[0].position == 1


async def test_review(client: SensCritique) -> None:
    details = await client.work_details(WORK_ID)
    assert details.url is not None
    # Reviews are fetched off the work's review listing to avoid pinning a
    # specific review id that could be deleted.
    data = await client._transport.graphql(
        "ProductReviews",
        """
        query ProductReviews($id: Int!) {
          product(id: $id) { reviews(limit: 1, offset: 0) { items { url } } }
        }
        """,
        {"id": WORK_ID},
    )
    url = data["product"]["reviews"]["items"][0]["url"]
    review = await client.review(url)
    assert review.body_html
    assert review.author_username
