"""Async facade: the public :class:`SensCritique` client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from ._parse import (
    coerce_universe,
    extract_numeric_id,
    parse_autocomplete_hit,
    parse_collection_item,
    parse_review,
    parse_shout,
    parse_user_profile,
    parse_user_search_hit,
    parse_work_details,
    parse_work_summary,
)
from ._queries import (
    AUTOCOMPLETE,
    COLLECTION,
    REVIEW,
    SEARCH,
    TOPCHART,
    USER_PROFILE,
    USER_SEARCH,
    WORK_DETAILS,
    WORK_REVIEWS,
    WORK_SHOUTS,
)
from ._transport import AsyncTransport, RateLimit, RetryConfig
from .errors import ParseError, UserNotFoundError
from .logger import build_logger
from .models import (
    AutocompleteHit,
    BulkError,
    BulkResult,
    CollectionAction,
    CollectionSort,
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

logger = build_logger("pysenscritique.client")

DEFAULT_PAGE_SIZE = 30
DEFAULT_SEASONS_LIMIT = 50


class SensCritique:
    """Read-only async client for the SensCritique GraphQL API.

    Use as an async context manager::

        async with SensCritique() as sc:
            async for item in sc.collection("some_user"):
                ...

    Rate limiting (1 request / 2.5 s) and retries are on by default; pass
    ``rate_limit=RateLimit(min_interval=0)`` to disable, or custom configs to
    tune. No credentials are handled anywhere (auth may be added later).
    """

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        rate_limit: RateLimit | None = None,
        retry: RetryConfig | None = None,
        timeout: httpx.Timeout | None = None,
        transport: AsyncTransport | None = None,
    ) -> None:
        if transport is not None:
            self._transport = transport
        else:
            kwargs: dict[str, Any] = {}
            if user_agent is not None:
                kwargs["user_agent"] = user_agent
            self._transport = AsyncTransport(
                rate_limit=rate_limit, retry=retry, timeout=timeout, **kwargs
            )

    async def __aenter__(self) -> SensCritique:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._transport.aclose()

    # -- collection ---------------------------------------------------------

    @staticmethod
    def _collection_filter_variables(
        genre_id: int | None,
        year_date_done: int | None,
        keywords: str | None,
        order: CollectionSort | str | None,
        is_agenda: bool | None,
    ) -> dict[str, Any]:
        variables: dict[str, Any] = {}
        if genre_id is not None:
            variables["genreId"] = genre_id
        if year_date_done is not None:
            variables["yearDateDone"] = year_date_done
        if keywords is not None:
            variables["keywords"] = keywords
        if order is not None:
            variables["order"] = CollectionSort(order).value
        if is_agenda is not None:
            variables["isAgenda"] = is_agenda
        return variables

    async def collection(
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
    ) -> AsyncIterator[UserCollectionItem]:
        """Iterate over a user's collection, page by page.

        Optional server-side filters: ``genre_id``, ``year_date_done`` (year
        the item was marked done), ``keywords`` (title search), ``order``
        (:class:`CollectionSort`), ``is_agenda``.

        Lenient by default: malformed items are logged and skipped. With
        ``strict=True`` the first malformed item raises :class:`ParseError`.
        Raises :class:`UserNotFoundError` for unknown usernames.
        """
        act = CollectionAction(action)
        filters = self._collection_filter_variables(
            genre_id, year_date_done, keywords, order, is_agenda
        )
        async for payload in self._collection_payloads(
            username, coerce_universe(universe), act, filters, page_size
        ):
            try:
                yield parse_collection_item(payload, act)
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed collection item",
                    extra={"username": username, "error": str(exc)},
                )

    async def collection_all(
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
        """Collect the whole collection, with a structured error report."""
        act = CollectionAction(action)
        filters = self._collection_filter_variables(
            genre_id, year_date_done, keywords, order, is_agenda
        )
        payloads = self._collection_payloads(
            username, coerce_universe(universe), act, filters, page_size
        )
        return await self._collect_items(
            payloads, lambda payload: parse_collection_item(payload, act), strict
        )

    async def _collection_payloads(
        self,
        username: str,
        universe: Universe,
        action: CollectionAction,
        filters: dict[str, Any],
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        offset = 0
        while True:
            data = await self._transport.graphql(
                "UserCollection",
                COLLECTION,
                {
                    **filters,
                    "username": username,
                    "universe": universe.value,
                    "action": action.value,
                    "offset": offset,
                    "limit": page_size,
                },
            )
            user = data.get("user")
            if user is None:
                raise UserNotFoundError(username)
            collection = user.get("collection") or {}
            total = collection.get("total") or 0
            products = collection.get("products") or []
            for product in products:
                yield product
            offset += len(products)
            if not products or offset >= total:
                return

    # -- users --------------------------------------------------------------

    async def user_profile(self, username: str) -> UserProfile:
        """Fetch a user's public profile, stats, and per-universe counts.

        Raises :class:`UserNotFoundError` for unknown usernames.
        """
        data = await self._transport.graphql(
            "UserProfile", USER_PROFILE, {"username": username}
        )
        user = data.get("user")
        if user is None:
            raise UserNotFoundError(username)
        return parse_user_profile(user)

    async def search_users(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[UserSearchHit]:
        """Search user accounts by name."""
        data = await self._transport.graphql(
            "SearchUsers",
            USER_SEARCH,
            {"query": query, "limit": limit, "offset": offset},
        )
        explorer = data.get("searchUserExplorer") or {}
        hits: list[UserSearchHit] = []
        for payload in explorer.get("items") or []:
            try:
                hits.append(parse_user_search_hit(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed user search result",
                    extra={"query": query, "error": str(exc)},
                )
        return hits

    # -- search -------------------------------------------------------------

    async def search(
        self,
        query: str,
        universe: Universe | str | None = None,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[WorkSummary]:
        """Search works, optionally restricted to one universe."""
        filters: list[dict[str, Any]] = []
        if universe is not None:
            filters.append(
                {
                    "identifier": "universe",
                    "termValues": [coerce_universe(universe).value],
                }
            )
        data = await self._transport.graphql(
            "SearchProducts",
            SEARCH,
            {"query": query, "offset": offset, "limit": limit, "filters": filters},
        )
        explorer = data.get("searchProductExplorer") or {}
        results: list[WorkSummary] = []
        for payload in explorer.get("items") or []:
            try:
                results.append(parse_work_summary(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed search result",
                    extra={"query": query, "error": str(exc)},
                )
        return results

    async def autocomplete(
        self,
        keywords: str,
        universe: Universe | str | None = None,
        *,
        limit: int = 10,
        strict: bool = False,
    ) -> list[AutocompleteHit]:
        """Instant-search suggestions: works and people mixed.

        Each hit carries either ``work`` or ``contact``, never both.
        """
        variables: dict[str, Any] = {"keywords": keywords, "limit": limit}
        if universe is not None:
            variables["universe"] = coerce_universe(universe).value
        data = await self._transport.graphql("Autocomplete", AUTOCOMPLETE, variables)
        payload = data.get("searchAutocomplete") or {}
        hits: list[AutocompleteHit] = []
        for item in payload.get("items") or []:
            try:
                hits.append(parse_autocomplete_hit(item))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed autocomplete item",
                    extra={"keywords": keywords, "error": str(exc)},
                )
        return hits

    # -- work details -------------------------------------------------------

    async def work_details(self, id_or_url: int | str) -> WorkDetails:
        """Fetch details for one work by numeric id or SensCritique URL."""
        work_id = extract_numeric_id(id_or_url, kind="work")
        data = await self._transport.graphql(
            "WorkDetails",
            WORK_DETAILS,
            {"id": work_id, "seasonsLimit": DEFAULT_SEASONS_LIMIT},
        )
        product = data.get("product")
        if product is None:
            raise ParseError(
                f"no product in response for id {work_id} (unknown id?)",
                payload=data,
            )
        return parse_work_details(product)

    # -- work reviews and shouts --------------------------------------------

    async def _product_listing_payloads(
        self,
        operation: str,
        query: str,
        field: str,
        work_id: int,
        variables: dict[str, Any],
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        offset = 0
        while True:
            data = await self._transport.graphql(
                operation,
                query,
                {**variables, "id": work_id, "limit": page_size, "offset": offset},
            )
            product = data.get("product")
            if product is None:
                raise ParseError(
                    f"no product in response for id {work_id} (unknown id?)",
                    payload=data,
                )
            listing = product.get(field) or {}
            total = listing.get("total") or 0
            items = listing.get("items") or []
            for item in items:
                yield item
            offset += len(items)
            if not items or offset >= total:
                return

    async def _lenient_items[T](
        self,
        payloads: AsyncIterator[dict[str, Any]],
        parser: Callable[[dict[str, Any]], T],
        label: str,
        strict: bool,
    ) -> AsyncIterator[T]:
        async for payload in payloads:
            try:
                yield parser(payload)
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed item",
                    extra={"kind": label, "error": str(exc)},
                )

    async def _collect_items[T](
        self,
        payloads: AsyncIterator[dict[str, Any]],
        parser: Callable[[dict[str, Any]], T],
        strict: bool,
    ) -> BulkResult[T]:
        items: list[T] = []
        errors: list[BulkError] = []
        async for payload in payloads:
            try:
                items.append(parser(payload))
            except ParseError as exc:
                if strict:
                    raise
                errors.append(
                    BulkError(
                        payload=exc.payload,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
        return BulkResult(items=items, errors=errors)

    @staticmethod
    def _review_listing_variables(
        filter: ReviewFilter | str | None, sort_by: ReviewSort | str | None
    ) -> dict[str, Any]:
        variables: dict[str, Any] = {}
        if filter is not None:
            variables["filter"] = ReviewFilter(filter).value
        if sort_by is not None:
            variables["sortBy"] = ReviewSort(sort_by).value
        return variables

    @staticmethod
    def _shout_listing_variables(order: ShoutSort | str | None) -> dict[str, Any]:
        variables: dict[str, Any] = {}
        if order is not None:
            variables["order"] = ShoutSort(order).value
        return variables

    def work_reviews(
        self,
        id_or_url: int | str,
        *,
        filter: ReviewFilter | str | None = None,
        sort_by: ReviewSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[Review]:
        """Iterate over a work's reviews, page by page."""
        payloads = self._product_listing_payloads(
            "WorkReviews",
            WORK_REVIEWS,
            "reviews",
            extract_numeric_id(id_or_url, kind="work"),
            self._review_listing_variables(filter, sort_by),
            page_size,
        )
        return self._lenient_items(payloads, parse_review, "review", strict)

    async def work_reviews_all(
        self,
        id_or_url: int | str,
        *,
        filter: ReviewFilter | str | None = None,
        sort_by: ReviewSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[Review]:
        """Collect all reviews of a work, with a structured error report."""
        payloads = self._product_listing_payloads(
            "WorkReviews",
            WORK_REVIEWS,
            "reviews",
            extract_numeric_id(id_or_url, kind="work"),
            self._review_listing_variables(filter, sort_by),
            page_size,
        )
        return await self._collect_items(payloads, parse_review, strict)

    def work_shouts(
        self,
        id_or_url: int | str,
        *,
        order: ShoutSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[ShoutSummary]:
        """Iterate over a work's shouts (short comments), page by page."""
        payloads = self._product_listing_payloads(
            "WorkShouts",
            WORK_SHOUTS,
            "shouts",
            extract_numeric_id(id_or_url, kind="work"),
            self._shout_listing_variables(order),
            page_size,
        )
        return self._lenient_items(payloads, parse_shout, "shout", strict)

    async def work_shouts_all(
        self,
        id_or_url: int | str,
        *,
        order: ShoutSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[ShoutSummary]:
        """Collect all shouts of a work, with a structured error report."""
        payloads = self._product_listing_payloads(
            "WorkShouts",
            WORK_SHOUTS,
            "shouts",
            extract_numeric_id(id_or_url, kind="work"),
            self._shout_listing_variables(order),
            page_size,
        )
        return await self._collect_items(payloads, parse_shout, strict)

    # -- topchart -----------------------------------------------------------

    async def topchart(
        self,
        universe: Universe | str = Universe.MOVIE,
        subtype: str = "TOP_111",
        *,
        limit: int | None = None,
        offset: int = 0,
        strict: bool = False,
    ) -> list[TopChartEntry]:
        """Fetch a generated topchart (e.g. the "Top 111" of a universe).

        ``subtype`` is one of the API's ``TopSubtype`` values:
        ``TOP_111``, ``TOP_111_ANIME``, ``TOP_100_OUT_OF_TOP_10``.
        """
        variables: dict[str, Any] = {
            "universe": coerce_universe(universe).value,
            "subtype": subtype,
            "offset": offset,
        }
        if limit is not None:
            variables["limit"] = limit
        data = await self._transport.graphql("Top", TOPCHART, variables)
        entries: list[TopChartEntry] = []
        for index, payload in enumerate(data.get("top") or []):
            try:
                entries.append(
                    TopChartEntry(
                        position=offset + index + 1,
                        work=parse_work_summary(payload),
                    )
                )
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed topchart entry", extra={"error": str(exc)}
                )
        return entries

    # -- reviews ------------------------------------------------------------

    async def review(self, url_or_id: int | str) -> Review:
        """Fetch a review by its numeric id or its URL.

        Review URLs look like ``/film/{slug}/critique/{id}`` (as returned in
        ``UserCollectionItem.review_url``).
        """
        review_id = extract_numeric_id(url_or_id, kind="review")
        data = await self._transport.graphql("ReviewById", REVIEW, {"id": review_id})
        payload = data.get("review")
        if payload is None:
            raise ParseError(
                f"no review in response for id {review_id} (unknown id?)",
                payload=data,
            )
        return parse_review(payload)
