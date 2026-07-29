"""Thin sync facade over the async client.

Runs a private event loop in a daemon thread so a single ``httpx.AsyncClient``
(and its rate limiter) persists across calls. Intended for scripts and the
REPL; async consumers (e.g. the MCP server) should use
:class:`~pysenscritique.client.SensCritique` directly.
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
    Review,
    TopChartEntry,
    Universe,
    UserCollectionItem,
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
            target=self._loop.run_forever, name="pysenscritique-sync", daemon=True
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
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[UserCollectionItem]:
        return self._iterate(
            self._client.collection(
                username, universe, action, strict=strict, page_size=page_size
            )
        )

    def collection_all(
        self,
        username: str,
        universe: Universe | str = Universe.MOVIE,
        action: CollectionAction | str = CollectionAction.DONE,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[UserCollectionItem]:
        return self._call(
            self._client.collection_all(
                username, universe, action, strict=strict, page_size=page_size
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
