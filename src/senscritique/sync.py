"""Thin sync facade over the async client.

Runs a private event loop in a daemon thread so a single ``httpx.AsyncClient``
(and its rate limiter) persists across calls. Intended for scripts and the
REPL; async consumers (e.g. the MCP server) should use
:class:`~senscritique.client.SensCritique` directly.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Coroutine, Iterator
from typing import Any, TypeVar

import httpx

from ._transport import RateLimit, RetryConfig
from .client import DEFAULT_PAGE_SIZE, SensCritique
from .models import (
    AutocompleteHit,
    BulkResult,
    CollectionAction,
    CollectionSort,
    ListItem,
    ListSearchHit,
    ListSummary,
    PollSearchHit,
    PollSummary,
    Review,
    ReviewFilter,
    ReviewSort,
    ShoutSort,
    ShoutSummary,
    TopChartEntry,
    Universe,
    UserCollectionItem,
    UserProfile,
    UserSearchHit,
    WorkDetails,
    WorkSummary,
)

T = TypeVar("T")


class SensCritiqueSync:
    """Blocking wrapper around :class:`SensCritique`.

    Use as a context manager or call :meth:`close` when done::

        with SensCritiqueSync() as sc:
            results = sc.search("dune", universe="movie")
    """

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        rate_limit: RateLimit | None = None,
        retry: RetryConfig | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="senscritique-sync", daemon=True
        )
        self._thread.start()
        # The transport's httpx client must be created on the loop thread so
        # its async primitives bind to the right event loop.
        self._client: SensCritique = self._call(
            self._make_client(
                user_agent=user_agent,
                rate_limit=rate_limit,
                retry=retry,
                timeout=timeout,
            )
        )

    @staticmethod
    async def _make_client(**kwargs: Any) -> SensCritique:
        return SensCritique(**kwargs)

    def _call(self, coro: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    @staticmethod
    async def _anext(aiterator: AsyncIterator[T]) -> T:
        return await anext(aiterator)

    def _iterate(self, aiterator: AsyncIterator[T]) -> Iterator[T]:
        while True:
            try:
                yield self._call(self._anext(aiterator))
            except StopAsyncIteration:
                return

    def __enter__(self) -> SensCritiqueSync:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        if self._loop.is_closed():
            return
        self._call(self._client.aclose())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()

    # -- operations ---------------------------------------------------------

    def collection(
        self,
        username: str,
        universe: Universe | str = Universe.MOVIE,
        action: CollectionAction | str = CollectionAction.DONE,
        *,
        genre_id: int | None = None,
        year_date_done: int | None = None,
        keywords: str | None = None,
        order: CollectionSort | str | None = None,
        is_agenda: bool | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[UserCollectionItem]:
        return self._iterate(
            self._client.collection(
                username,
                universe,
                action,
                genre_id=genre_id,
                year_date_done=year_date_done,
                keywords=keywords,
                order=order,
                is_agenda=is_agenda,
                strict=strict,
                page_size=page_size,
            )
        )

    def collection_all(
        self,
        username: str,
        universe: Universe | str = Universe.MOVIE,
        action: CollectionAction | str = CollectionAction.DONE,
        *,
        genre_id: int | None = None,
        year_date_done: int | None = None,
        keywords: str | None = None,
        order: CollectionSort | str | None = None,
        is_agenda: bool | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[UserCollectionItem]:
        return self._call(
            self._client.collection_all(
                username,
                universe,
                action,
                genre_id=genre_id,
                year_date_done=year_date_done,
                keywords=keywords,
                order=order,
                is_agenda=is_agenda,
                strict=strict,
                page_size=page_size,
            )
        )

    def user_profile(self, username: str) -> UserProfile:
        return self._call(self._client.user_profile(username))

    def search_users(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[UserSearchHit]:
        return self._call(
            self._client.search_users(
                query, limit=limit, offset=offset, strict=strict
            )
        )

    def search(
        self,
        query: str,
        universe: Universe | str | None = None,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[WorkSummary]:
        return self._call(
            self._client.search(
                query, universe, limit=limit, offset=offset, strict=strict
            )
        )

    def autocomplete(
        self,
        keywords: str,
        universe: Universe | str | None = None,
        *,
        limit: int = 10,
        strict: bool = False,
    ) -> list[AutocompleteHit]:
        return self._call(
            self._client.autocomplete(keywords, universe, limit=limit, strict=strict)
        )

    def work_details(self, id_or_url: int | str) -> WorkDetails:
        return self._call(self._client.work_details(id_or_url))

    def work_reviews(
        self,
        id_or_url: int | str,
        *,
        filter: ReviewFilter | str | None = None,
        sort_by: ReviewSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[Review]:
        return self._iterate(
            self._client.work_reviews(
                id_or_url,
                filter=filter,
                sort_by=sort_by,
                strict=strict,
                page_size=page_size,
            )
        )

    def work_reviews_all(
        self,
        id_or_url: int | str,
        *,
        filter: ReviewFilter | str | None = None,
        sort_by: ReviewSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[Review]:
        return self._call(
            self._client.work_reviews_all(
                id_or_url,
                filter=filter,
                sort_by=sort_by,
                strict=strict,
                page_size=page_size,
            )
        )

    def work_shouts(
        self,
        id_or_url: int | str,
        *,
        order: ShoutSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[ShoutSummary]:
        return self._iterate(
            self._client.work_shouts(
                id_or_url, order=order, strict=strict, page_size=page_size
            )
        )

    def work_shouts_all(
        self,
        id_or_url: int | str,
        *,
        order: ShoutSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[ShoutSummary]:
        return self._call(
            self._client.work_shouts_all(
                id_or_url, order=order, strict=strict, page_size=page_size
            )
        )

    def topchart(
        self,
        universe: Universe | str = Universe.MOVIE,
        subtype: str = "TOP_111",
        *,
        limit: int | None = None,
        offset: int = 0,
        strict: bool = False,
    ) -> list[TopChartEntry]:
        return self._call(
            self._client.topchart(
                universe, subtype, limit=limit, offset=offset, strict=strict
            )
        )

    def review(self, url_or_id: int | str) -> Review:
        return self._call(self._client.review(url_or_id))

    def list_details(self, id_or_url: int | str) -> ListSummary:
        return self._call(self._client.list_details(id_or_url))

    def list_items(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[ListItem]:
        return self._iterate(
            self._client.list_items(id_or_url, strict=strict, page_size=page_size)
        )

    def list_items_all(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[ListItem]:
        return self._call(
            self._client.list_items_all(
                id_or_url, strict=strict, page_size=page_size
            )
        )

    def search_lists(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[ListSearchHit]:
        return self._call(
            self._client.search_lists(
                query, limit=limit, offset=offset, strict=strict
            )
        )

    def top10_list(self, universe: Universe | str = Universe.MOVIE) -> ListSummary:
        return self._call(self._client.top10_list(universe))

    def poll(self, id_or_url: int | str) -> PollSummary:
        return self._call(self._client.poll(id_or_url))

    def poll_works(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[WorkSummary]:
        return self._iterate(
            self._client.poll_works(id_or_url, strict=strict, page_size=page_size)
        )

    def poll_works_all(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        return self._call(
            self._client.poll_works_all(
                id_or_url, strict=strict, page_size=page_size
            )
        )

    def top_polls(self, *, strict: bool = False) -> list[PollSummary]:
        return self._call(self._client.top_polls(strict=strict))

    def polls(
        self,
        universe: Universe | str | None = None,
        *,
        limit: int = 10,
        offset: int = 0,
        sort_by: str | None = None,
        strict: bool = False,
    ) -> list[PollSummary]:
        return self._call(
            self._client.polls(
                universe, limit=limit, offset=offset, sort_by=sort_by, strict=strict
            )
        )

    def search_polls(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[PollSearchHit]:
        return self._call(
            self._client.search_polls(
                query, limit=limit, offset=offset, strict=strict
            )
        )
