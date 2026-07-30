"""Live integration tests against the real SensCritique API.

Marked ``integration`` and skipped in default runs. Run manually with
``make test-integration``. One cheap canary per operation family, sharing a
module-scoped client so the default rate limiter (1 request / 2.5 s) spaces
every call: roughly 30 requests, so about 75 seconds. Page sizes stay tiny
on purpose; these tests exist to catch contract drift, not to fetch data.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from senscritique import (
    CollectionAction,
    CollectionSort,
    SensCritique,
    Universe,
    UserNotFoundError,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

# Public account with a mid-sized collection (also used by the s2l project).
USERNAME = "vsv"
# "L'Aurore" (Sunrise, 1927), a stable classic with plenty of reviews.
WORK_ID = 451178
# Steven Spielberg, a person who will not be deleted any time soon.
CONTACT_ID = 993
# The "Dune" franchise, reachable from any Dune work's `franchises`.
FRANCHISE_ID = 260


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


async def test_autocomplete(client: SensCritique) -> None:
    hits = await client.autocomplete("dune", limit=5)
    assert hits
    assert any(hit.work is not None for hit in hits)


async def test_collection_filters(client: SensCritique) -> None:
    items = []
    async for item in client.collection(
        USERNAME,
        Universe.MOVIE,
        CollectionAction.DONE,
        keywords="dune",
        order=CollectionSort.RATING_DESC,
        page_size=3,
    ):
        items.append(item)
        if len(items) >= 3:
            break
    assert all("une" in item.work.title for item in items)


async def test_user_profile(client: SensCritique) -> None:
    profile = await client.user_profile(USERNAME)
    assert profile.username == USERNAME
    assert profile.stats is not None
    assert profile.rating_counts


async def test_search_users(client: SensCritique) -> None:
    hits = await client.search_users(USERNAME, limit=3)
    assert hits
    assert all(hit.id > 0 for hit in hits)


async def test_work_reviews_first_page(client: SensCritique) -> None:
    reviews = []
    async for review in client.work_reviews(WORK_ID, page_size=3):
        reviews.append(review)
        if len(reviews) >= 3:
            break
    assert reviews
    assert all(review.url for review in reviews)


async def test_work_shouts_first_page(client: SensCritique) -> None:
    shouts = []
    async for shout in client.work_shouts(WORK_ID, page_size=3):
        shouts.append(shout)
        if len(shouts) >= 3:
            break
    assert all(shout.id > 0 for shout in shouts)


async def test_lists(client: SensCritique) -> None:
    hits = await client.search_lists("science-fiction", limit=3)
    assert hits
    details = await client.list_details(hits[0].id)
    assert details.id == hits[0].id
    items = []
    async for item in client.list_items(details.id, page_size=3):
        items.append(item)
        if len(items) >= 3:
            break
    assert items
    assert all(item.work.id > 0 for item in items)


async def test_top10_list(client: SensCritique) -> None:
    details = await client.top10_list(Universe.MOVIE)
    # Neither is_official nor product_count is set on this generated list.
    assert details.label
    assert details.author_username == "senscritique"


async def test_polls(client: SensCritique) -> None:
    polls = await client.top_polls()
    assert polls
    works = []
    async for work in client.poll_works(polls[0].id, page_size=3):
        works.append(work)
        if len(works) >= 3:
            break
    assert works


async def test_polls_browse_and_search(client: SensCritique) -> None:
    browsed = await client.polls(Universe.MOVIE, limit=3)
    assert browsed
    hits = await client.search_polls("2020", limit=3)
    assert hits


async def test_genres_and_genre_products(client: SensCritique) -> None:
    genres = await client.genres(Universe.MOVIE)
    assert len(genres) > 10
    works = []
    async for work in client.genre_products(
        Universe.MOVIE, genres[0].id, order="RATING_DESC", page_size=3
    ):
        works.append(work)
        if len(works) >= 3:
            break
    assert len(works) == 3
    assert all(work.universe is Universe.MOVIE for work in works)


async def test_products_by_release(client: SensCritique) -> None:
    works = []
    async for work in client.products_by_release(
        Universe.MOVIE, year=2025, sort_by="RATING", page_size=3
    ):
        works.append(work)
        if len(works) >= 3:
            break
    # The year filter is on the release date, which can differ from the
    # production year (a 1993 concert film reissued in 2025), so only the
    # request shape is asserted here.
    assert works
    assert all(work.id > 0 for work in works)


async def test_products_by_month_and_day(client: SensCritique) -> None:
    # Never use the `_all` collectors here: a month of releases is hundreds
    # of rate-limited pages. One page of each field is enough for a canary.
    month = []
    async for work in client.products_by_month(2025, 6, page_size=3):
        month.append(work)
        if len(month) >= 3:
            break
    assert month
    # 4 June 2025 is a Wednesday: French releases cluster there, and the
    # API's "week" field really returns that one day (see docs/api/browse.md).
    day = []
    async for work in client.products_by_day(2025, 6, 4, page_size=3):
        day.append(work)
        if len(day) >= 3:
            break
    assert day


async def test_group_products(client: SensCritique) -> None:
    works = []
    async for work in client.group_products(
        FRANCHISE_ID, Universe.MOVIE, page_size=3
    ):
        works.append(work)
        if len(works) >= 3:
            break
    assert works
    assert all(work.universe is Universe.MOVIE for work in works)


async def test_providers_and_streaming(client: SensCritique) -> None:
    providers = await client.providers()
    assert providers
    works = []
    async for work in client.streaming_explorer(
        Universe.MOVIE,
        provider_ids=[providers[0].id],
        order="RATING_DESC",
        page_size=3,
    ):
        works.append(work)
        if len(works) >= 3:
            break
    assert len(works) == 3


async def test_discover_products(client: SensCritique) -> None:
    discovery = await client.discover_products(Universe.MOVIE)
    # Random draw: the public slots can come back empty, but not both.
    assert discovery.fresh is not None or discovery.popular is not None


async def test_contact_and_credits(client: SensCritique) -> None:
    contact = await client.contact(CONTACT_ID)
    assert contact.name == "Steven Spielberg"
    assert "movie" in contact.product_counts
    assert contact.date_of_birth is not None
    assert contact.date_of_birth.day == 18
    works = []
    async for work in client.contact_products(
        CONTACT_ID, Universe.MOVIE, profession="directors", page_size=3
    ):
        works.append(work)
        if len(works) >= 3:
            break
    assert len(works) == 3


async def test_search_contacts(client: SensCritique) -> None:
    hits = await client.search_contacts("murnau", limit=3)
    assert hits
    assert any("Murnau" in hit.name for hit in hits)
