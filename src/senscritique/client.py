"""Async facade: the public :class:`SensCritique` client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

import httpx

from ._parse import (
    coerce_universe,
    extract_numeric_id,
    parse_autocomplete_hit,
    parse_collection_item,
    parse_contact_details,
    parse_contact_search_hit,
    parse_discovery,
    parse_genre,
    parse_list_item,
    parse_list_search_hit,
    parse_list_summary,
    parse_poll_search_hit,
    parse_poll_summary,
    parse_review,
    parse_shout,
    parse_streaming_provider,
    parse_user_profile,
    parse_user_search_hit,
    parse_work_details,
    parse_work_summary,
)
from ._queries import (
    AUTOCOMPLETE,
    COLLECTION,
    CONTACT,
    CONTACT_PRODUCTS,
    CONTACT_SEARCH,
    DISCOVER_PRODUCTS,
    GENRE_PRODUCTS,
    GENRES,
    GROUP_PRODUCTS,
    LIST_DETAILS,
    LIST_ITEMS,
    LIST_SEARCH,
    POLL_DETAILS,
    POLL_SEARCH,
    POLL_WORKS,
    POLLS,
    PRODUCTS_BY_MONTH,
    PRODUCTS_BY_RELEASE,
    PRODUCTS_BY_WEEK,
    PROVIDERS,
    REVIEW,
    SEARCH,
    STREAMING_EXPLORER,
    TOP10_LIST,
    TOP_POLLS,
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
    ContactDetails,
    ContactProductSort,
    ContactSearchHit,
    Discovery,
    DiscoveryMood,
    DiscoveryType,
    Genre,
    GenreSort,
    GroupSort,
    ListItem,
    ListSearchHit,
    ListSummary,
    PollSearchHit,
    PollSummary,
    ReleaseSort,
    Review,
    ReviewFilter,
    ReviewSort,
    ShoutSort,
    ShoutSummary,
    StreamingProvider,
    StreamingSort,
    TopChartEntry,
    Universe,
    UserCollectionItem,
    UserProfile,
    UserSearchHit,
    WorkDetails,
    WorkSummary,
)

logger = build_logger("senscritique.client")

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

    async def _listing_payloads(
        self,
        operation: str,
        query: str,
        variables: dict[str, Any],
        page_size: int,
        *,
        root: str,
        items_key: str | None = "items",
        total_key: str | None = "total",
    ) -> AsyncIterator[dict[str, Any]]:
        """Paginate a root listing field.

        ``items_key=None`` means the root field is itself the item list;
        ``total_key=None`` means the payload exposes no total, so iteration
        stops on the first short page (as for ``Poll.products``).
        """
        offset = 0
        while True:
            data = await self._transport.graphql(
                operation,
                query,
                {**variables, "limit": page_size, "offset": offset},
            )
            payload = data.get(root)
            if payload is None:
                return
            total: int | None = None
            if items_key is None:
                items = payload if isinstance(payload, list) else []
            else:
                items = payload.get(items_key) or []
                if total_key is not None:
                    total = payload.get(total_key)
            for item in items:
                yield item
            offset += len(items)
            if not items:
                return
            if total is not None:
                if offset >= total:
                    return
            elif len(items) < page_size:
                return

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

    # -- lists --------------------------------------------------------------

    async def list_details(self, id_or_url: int | str) -> ListSummary:
        """Fetch a list's metadata (label, author, counts) without items."""
        list_id = extract_numeric_id(id_or_url, kind="list")
        data = await self._transport.graphql(
            "ListDetails", LIST_DETAILS, {"id": list_id}
        )
        payload = data.get("userList")
        if payload is None:
            raise ParseError(
                f"no list in response for id {list_id} (unknown id?)",
                payload=data,
            )
        return parse_list_summary(payload)

    async def _list_item_payloads(
        self, list_id: int, page_size: int
    ) -> AsyncIterator[dict[str, Any]]:
        offset = 0
        while True:
            data = await self._transport.graphql(
                "ListItems",
                LIST_ITEMS,
                {"id": list_id, "limit": page_size, "offset": offset},
            )
            payload = data.get("userList")
            if payload is None:
                raise ParseError(
                    f"no list in response for id {list_id} (unknown id?)",
                    payload=data,
                )
            listing = payload.get("productsList") or {}
            total = listing.get("total") or 0
            items = listing.get("items") or []
            for item in items:
                yield item
            offset += len(items)
            if not items or offset >= total:
                return

    def list_items(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[ListItem]:
        """Iterate over a list's items (work, position, annotation)."""
        payloads = self._list_item_payloads(
            extract_numeric_id(id_or_url, kind="list"), page_size
        )
        return self._lenient_items(payloads, parse_list_item, "list item", strict)

    async def list_items_all(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[ListItem]:
        """Collect all items of a list, with a structured error report."""
        payloads = self._list_item_payloads(
            extract_numeric_id(id_or_url, kind="list"), page_size
        )
        return await self._collect_items(payloads, parse_list_item, strict)

    async def search_lists(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[ListSearchHit]:
        """Search lists by title."""
        data = await self._transport.graphql(
            "SearchLists",
            LIST_SEARCH,
            {"query": query, "limit": limit, "offset": offset},
        )
        explorer = data.get("searchListExplorer") or {}
        hits: list[ListSearchHit] = []
        for payload in explorer.get("items") or []:
            try:
                hits.append(parse_list_search_hit(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed list search result",
                    extra={"query": query, "error": str(exc)},
                )
        return hits

    async def top10_list(
        self, universe: Universe | str = Universe.MOVIE
    ) -> ListSummary:
        """Fetch the site's aggregated "Top 100 of Top 10s" list metadata.

        Use :meth:`list_items` with the returned id to read its entries.
        """
        data = await self._transport.graphql(
            "GetTop10", TOP10_LIST, {"universe": coerce_universe(universe).value}
        )
        payload = data.get("getTop10")
        if payload is None:
            raise ParseError("no list in getTop10 response", payload=data)
        return parse_list_summary(payload)

    # -- polls --------------------------------------------------------------

    async def poll(self, id_or_url: int | str) -> PollSummary:
        """Fetch a poll's metadata without its ranked works."""
        poll_id = extract_numeric_id(id_or_url, kind="poll")
        data = await self._transport.graphql(
            "PollDetails", POLL_DETAILS, {"id": poll_id}
        )
        payload = data.get("poll")
        if payload is None:
            raise ParseError(
                f"no poll in response for id {poll_id} (unknown id?)",
                payload=data,
            )
        return parse_poll_summary(payload)

    async def _poll_work_payloads(
        self, poll_id: int, page_size: int
    ) -> AsyncIterator[dict[str, Any]]:
        # Poll.products exposes no total; stop on the first short page.
        offset = 0
        while True:
            data = await self._transport.graphql(
                "PollWorks",
                POLL_WORKS,
                {"id": poll_id, "limit": page_size, "offset": offset},
            )
            payload = data.get("poll")
            if payload is None:
                raise ParseError(
                    f"no poll in response for id {poll_id} (unknown id?)",
                    payload=data,
                )
            items = payload.get("products") or []
            for item in items:
                yield item
            if len(items) < page_size:
                return
            offset += len(items)

    def poll_works(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Iterate over a poll's ranked works."""
        payloads = self._poll_work_payloads(
            extract_numeric_id(id_or_url, kind="poll"), page_size
        )
        return self._lenient_items(payloads, parse_work_summary, "poll work", strict)

    async def poll_works_all(
        self,
        id_or_url: int | str,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect all ranked works of a poll, with an error report."""
        payloads = self._poll_work_payloads(
            extract_numeric_id(id_or_url, kind="poll"), page_size
        )
        return await self._collect_items(payloads, parse_work_summary, strict)

    async def top_polls(self, *, strict: bool = False) -> list[PollSummary]:
        """Fetch the currently featured polls."""
        data = await self._transport.graphql("TopPolls", TOP_POLLS, {})
        return self._parse_poll_list(data.get("topPolls") or [], strict)

    async def polls(
        self,
        universe: Universe | str | None = None,
        *,
        limit: int = 10,
        offset: int = 0,
        sort_by: str | None = None,
        strict: bool = False,
    ) -> list[PollSummary]:
        """Browse polls, optionally by universe.

        ``sort_by`` is one of the API's ``PollSortBy`` values (``ALL``,
        ``NEW``, ``COMPLETE``, ``INCOMPLETE``, ``NOT_STARTED``); completion
        states are meaningless without auth.
        """
        variables: dict[str, Any] = {"limit": limit, "offset": offset}
        if universe is not None:
            variables["universe"] = coerce_universe(universe).value
        if sort_by is not None:
            variables["sortBy"] = sort_by
        data = await self._transport.graphql("PollsList", POLLS, variables)
        payload = data.get("polls") or {}
        return self._parse_poll_list(payload.get("items") or [], strict)

    def _parse_poll_list(
        self, payloads: list[dict[str, Any]], strict: bool
    ) -> list[PollSummary]:
        results: list[PollSummary] = []
        for payload in payloads:
            try:
                results.append(parse_poll_summary(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed poll", extra={"error": str(exc)}
                )
        return results

    async def search_polls(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[PollSearchHit]:
        """Search polls by title."""
        data = await self._transport.graphql(
            "SearchPolls",
            POLL_SEARCH,
            {"query": query, "limit": limit, "offset": offset},
        )
        explorer = data.get("searchPollExplorer") or {}
        hits: list[PollSearchHit] = []
        for payload in explorer.get("items") or []:
            try:
                hits.append(parse_poll_search_hit(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed poll search result",
                    extra={"query": query, "error": str(exc)},
                )
        return hits

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

    # -- genres -------------------------------------------------------------

    async def genres(
        self, universe: Universe | str = Universe.MOVIE, *, strict: bool = False
    ) -> list[Genre]:
        """List a universe's genres.

        Genre ids (never labels) are what :meth:`genre_products` and the
        ``genre_id`` collection filter expect; ids differ per universe.
        """
        data = await self._transport.graphql(
            "Genres", GENRES, {"universe": coerce_universe(universe).value}
        )
        genres: list[Genre] = []
        for payload in data.get("genres") or []:
            try:
                genres.append(parse_genre(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed genre", extra={"error": str(exc)}
                )
        return genres

    def _genre_product_payloads(
        self,
        universe: Universe | str,
        genre_id: int | None,
        order: GenreSort | str | None,
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        variables: dict[str, Any] = {"universe": coerce_universe(universe).value}
        if genre_id is not None:
            variables["genre"] = genre_id
        if order is not None:
            variables["order"] = GenreSort(order).value
        return self._listing_payloads(
            "GenreProducts",
            GENRE_PRODUCTS,
            variables,
            page_size,
            root="genreProducts",
            items_key="products",
        )

    def genre_products(
        self,
        universe: Universe | str = Universe.MOVIE,
        genre_id: int | None = None,
        *,
        order: GenreSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Browse a universe's works, optionally narrowed to one genre.

        ``genre_id`` comes from :meth:`genres`; omitting it browses the whole
        universe.
        """
        payloads = self._genre_product_payloads(
            universe, genre_id, order, page_size
        )
        return self._lenient_items(
            payloads, parse_work_summary, "genre product", strict
        )

    async def genre_products_all(
        self,
        universe: Universe | str = Universe.MOVIE,
        genre_id: int | None = None,
        *,
        order: GenreSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect a genre listing, with a structured error report.

        A universe holds six figures of works; pass ``genre_id`` and expect a
        long, rate-limited walk.
        """
        payloads = self._genre_product_payloads(
            universe, genre_id, order, page_size
        )
        return await self._collect_items(payloads, parse_work_summary, strict)

    # -- releases -----------------------------------------------------------

    def _release_payloads(
        self,
        universe: Universe | str,
        year: int | None,
        sort_by: ReleaseSort | str | None,
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        variables: dict[str, Any] = {"universe": coerce_universe(universe).value}
        if year is not None:
            # The year is only honored alongside byPeriod/period (verified
            # live: passing it alone returns the whole universe).
            variables["year"] = year
            variables["byPeriod"] = True
            variables["period"] = "OUTBYYEAR"
        if sort_by is not None:
            variables["sortBy"] = ReleaseSort(sort_by).value
        return self._listing_payloads(
            "ProductsByRelease",
            PRODUCTS_BY_RELEASE,
            variables,
            page_size,
            root="productsByRelease",
        )

    def products_by_release(
        self,
        universe: Universe | str = Universe.MOVIE,
        *,
        year: int | None = None,
        sort_by: ReleaseSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Browse a universe by release, most recent releases first.

        ``year`` narrows to one release year; without it the listing spans the
        whole universe.
        """
        payloads = self._release_payloads(universe, year, sort_by, page_size)
        return self._lenient_items(payloads, parse_work_summary, "release", strict)

    async def products_by_release_all(
        self,
        universe: Universe | str = Universe.MOVIE,
        *,
        year: int | None = None,
        sort_by: ReleaseSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect a release listing, with a structured error report."""
        payloads = self._release_payloads(universe, year, sort_by, page_size)
        return await self._collect_items(payloads, parse_work_summary, strict)

    def _month_payloads(
        self,
        operation: str,
        query: str,
        root: str,
        variables: dict[str, Any],
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        # Both fields return a bare product list with no total.
        return self._listing_payloads(
            operation,
            query,
            variables,
            page_size,
            root=root,
            items_key=None,
            total_key=None,
        )

    def products_by_month(
        self,
        year: int,
        month: int,
        universe: Universe | str = Universe.MOVIE,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Browse the works released in one calendar month."""
        payloads = self._month_payloads(
            "ProductsByMonth",
            PRODUCTS_BY_MONTH,
            "productsByMonth",
            {
                "universe": coerce_universe(universe).value,
                "year": year,
                "month": month,
            },
            page_size,
        )
        return self._lenient_items(payloads, parse_work_summary, "release", strict)

    async def products_by_month_all(
        self,
        year: int,
        month: int,
        universe: Universe | str = Universe.MOVIE,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect one month of releases, with a structured error report."""
        payloads = self._month_payloads(
            "ProductsByMonth",
            PRODUCTS_BY_MONTH,
            "productsByMonth",
            {
                "universe": coerce_universe(universe).value,
                "year": year,
                "month": month,
            },
            page_size,
        )
        return await self._collect_items(payloads, parse_work_summary, strict)

    def products_by_day(
        self,
        year: int,
        month: int,
        day: int,
        universe: Universe | str = Universe.MOVIE,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Browse the works released on one exact date.

        Backed by the API's misnamed ``productsByWeek`` field, which returns
        a single day, not a week (verified live: 5 movies for 2025-06-04, none
        for the day before). Most French releases land on Wednesdays.
        """
        payloads = self._month_payloads(
            "ProductsByWeek",
            PRODUCTS_BY_WEEK,
            "productsByWeek",
            {
                "universe": coerce_universe(universe).value,
                "year": year,
                "month": month,
                "day": day,
            },
            page_size,
        )
        return self._lenient_items(payloads, parse_work_summary, "release", strict)

    async def products_by_day_all(
        self,
        year: int,
        month: int,
        day: int,
        universe: Universe | str = Universe.MOVIE,
        *,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect one day of releases, with a structured error report."""
        payloads = self._month_payloads(
            "ProductsByWeek",
            PRODUCTS_BY_WEEK,
            "productsByWeek",
            {
                "universe": coerce_universe(universe).value,
                "year": year,
                "month": month,
                "day": day,
            },
            page_size,
        )
        return await self._collect_items(payloads, parse_work_summary, strict)

    # -- franchises ---------------------------------------------------------

    def _group_product_payloads(
        self,
        franchise_id: int,
        universe: Universe | str | None,
        order: GroupSort | str | None,
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        variables: dict[str, Any] = {"franchiseId": franchise_id}
        if universe is not None:
            variables["universe"] = coerce_universe(universe).value
        if order is not None:
            variables["order"] = GroupSort(order).value
        # GroupProducts echoes limit/offset but exposes no total.
        return self._listing_payloads(
            "GroupProducts",
            GROUP_PRODUCTS,
            variables,
            page_size,
            root="groupProducts",
            total_key=None,
        )

    def group_products(
        self,
        franchise_id: int,
        universe: Universe | str | None = None,
        *,
        order: GroupSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Iterate over the contents of a franchise.

        ``franchise_id`` is :attr:`Franchise.id` from
        :meth:`work_details` (the ``/groupe/`` URL segment). A franchise spans
        universes: without a ``universe`` filter, works of unmapped universes
        (games, albums...) are skipped leniently.
        """
        payloads = self._group_product_payloads(
            franchise_id, universe, order, page_size
        )
        return self._lenient_items(
            payloads, parse_work_summary, "franchise product", strict
        )

    async def group_products_all(
        self,
        franchise_id: int,
        universe: Universe | str | None = None,
        *,
        order: GroupSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect a franchise's contents, with a structured error report."""
        payloads = self._group_product_payloads(
            franchise_id, universe, order, page_size
        )
        return await self._collect_items(payloads, parse_work_summary, strict)

    # -- streaming ----------------------------------------------------------

    async def providers(self, *, strict: bool = False) -> list[StreamingProvider]:
        """List the streaming services SensCritique knows about.

        Ids feed :meth:`streaming_explorer` and match
        :attr:`Provider.provider_id` on work details.
        """
        data = await self._transport.graphql("Providers", PROVIDERS, {})
        providers: list[StreamingProvider] = []
        for payload in data.get("providers") or []:
            try:
                providers.append(parse_streaming_provider(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed provider", extra={"error": str(exc)}
                )
        return providers

    def _streaming_payloads(
        self,
        universe: Universe | str,
        provider_ids: Sequence[int] | None,
        genre_ids: Sequence[int] | None,
        years: Sequence[int] | None,
        ratings: Sequence[int] | None,
        country_ids: Sequence[int] | None,
        only_popular: bool | None,
        order: StreamingSort | str | None,
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        variables: dict[str, Any] = {"subtype": coerce_universe(universe).value}
        if provider_ids is not None:
            variables["providers"] = list(provider_ids)
        if genre_ids is not None:
            variables["genres"] = list(genre_ids)
        if years is not None:
            variables["yearDateRelease"] = list(years)
        if ratings is not None:
            variables["rating"] = list(ratings)
        if country_ids is not None:
            variables["countries"] = list(country_ids)
        if only_popular is not None:
            variables["onlyPopular"] = only_popular
        if order is not None:
            variables["order"] = StreamingSort(order).value
        return self._listing_payloads(
            "StreamingExplorer",
            STREAMING_EXPLORER,
            variables,
            page_size,
            root="streamingExplorer",
            items_key="products",
        )

    def streaming_explorer(
        self,
        universe: Universe | str = Universe.MOVIE,
        *,
        provider_ids: Sequence[int] | None = None,
        genre_ids: Sequence[int] | None = None,
        years: Sequence[int] | None = None,
        ratings: Sequence[int] | None = None,
        country_ids: Sequence[int] | None = None,
        only_popular: bool | None = None,
        order: StreamingSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Browse what is streaming, filtered like the site's explorer.

        ``provider_ids`` come from :meth:`providers`, ``genre_ids`` from
        :meth:`genres`; ``years`` and ``ratings`` are inclusive
        ``[min, max]`` bounds. The API's own filter facets (countries, period)
        and its per-user ``myProviders`` are not exposed.
        """
        payloads = self._streaming_payloads(
            universe,
            provider_ids,
            genre_ids,
            years,
            ratings,
            country_ids,
            only_popular,
            order,
            page_size,
        )
        return self._lenient_items(
            payloads, parse_work_summary, "streaming product", strict
        )

    async def streaming_explorer_all(
        self,
        universe: Universe | str = Universe.MOVIE,
        *,
        provider_ids: Sequence[int] | None = None,
        genre_ids: Sequence[int] | None = None,
        years: Sequence[int] | None = None,
        ratings: Sequence[int] | None = None,
        country_ids: Sequence[int] | None = None,
        only_popular: bool | None = None,
        order: StreamingSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect a streaming listing, with a structured error report."""
        payloads = self._streaming_payloads(
            universe,
            provider_ids,
            genre_ids,
            years,
            ratings,
            country_ids,
            only_popular,
            order,
            page_size,
        )
        return await self._collect_items(payloads, parse_work_summary, strict)

    # -- discovery ----------------------------------------------------------

    async def discover_products(
        self,
        universe: Universe | str = Universe.MOVIE,
        *,
        mood: DiscoveryMood | str | None = None,
        type: DiscoveryType | str | None = None,
        excluded_ids: Sequence[int] | None = None,
    ) -> Discovery:
        """Draw suggestions from the site's discovery roulette.

        Returns the two public slots (a fresh release and a popular work);
        the wish/recommendation slots need a session and stay ``None``. Pass
        ``excluded_ids`` to re-draw without works already seen.
        """
        variables: dict[str, Any] = {"universe": coerce_universe(universe).value}
        if mood is not None:
            variables["mood"] = DiscoveryMood(mood).value
        if type is not None:
            variables["type"] = DiscoveryType(type).value
        if excluded_ids is not None:
            variables["excludedProductIds"] = list(excluded_ids)
        data = await self._transport.graphql(
            "DiscoverProducts", DISCOVER_PRODUCTS, variables
        )
        payload = data.get("discoverProducts")
        if payload is None:
            raise ParseError("no discoverProducts in response", payload=data)
        return parse_discovery(payload)

    # -- people -------------------------------------------------------------

    async def contact(self, id_or_url: int | str) -> ContactDetails:
        """Fetch a person (or company/group) by numeric id or URL.

        People URLs look like ``/contact/{slug}/{id}``, as returned by
        :meth:`autocomplete` and :meth:`search_contacts`.
        """
        contact_id = extract_numeric_id(id_or_url, kind="contact")
        data = await self._transport.graphql("Contact", CONTACT, {"id": contact_id})
        payload = data.get("contact")
        if payload is None:
            raise ParseError(
                f"no contact in response for id {contact_id} (unknown id?)",
                payload=data,
            )
        return parse_contact_details(payload)

    async def _contact_product_payloads(
        self,
        contact_id: int,
        variables: dict[str, Any],
        page_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        offset = 0
        while True:
            data = await self._transport.graphql(
                "ContactProducts",
                CONTACT_PRODUCTS,
                {
                    **variables,
                    "id": contact_id,
                    "limit": page_size,
                    "offset": offset,
                },
            )
            contact = data.get("contact")
            if contact is None:
                raise ParseError(
                    f"no contact in response for id {contact_id} (unknown id?)",
                    payload=data,
                )
            listing = contact.get("productsList") or {}
            total = listing.get("total") or 0
            items = listing.get("items") or []
            for item in items:
                yield item
            offset += len(items)
            if not items or offset >= total:
                return

    @staticmethod
    def _contact_product_variables(
        universe: Universe | str | None,
        profession: str | None,
        order: ContactProductSort | str | None,
    ) -> dict[str, Any]:
        variables: dict[str, Any] = {}
        if universe is not None:
            variables["universe"] = coerce_universe(universe).value
        if profession is not None:
            variables["profession"] = profession
        if order is not None:
            variables["order"] = ContactProductSort(order).value
        return variables

    def contact_products(
        self,
        id_or_url: int | str,
        universe: Universe | str | None = None,
        *,
        profession: str | None = None,
        order: ContactProductSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[WorkSummary]:
        """Iterate over the works a person is credited on.

        ``profession`` is one of the raw API tags exposed as
        :attr:`ContactDetails.professions` (``"directors"``, ``"actors"``,
        ``"producers"``...); without it, every credit is returned.
        """
        payloads = self._contact_product_payloads(
            extract_numeric_id(id_or_url, kind="contact"),
            self._contact_product_variables(universe, profession, order),
            page_size,
        )
        return self._lenient_items(
            payloads, parse_work_summary, "contact product", strict
        )

    async def contact_products_all(
        self,
        id_or_url: int | str,
        universe: Universe | str | None = None,
        *,
        profession: str | None = None,
        order: ContactProductSort | str | None = None,
        strict: bool = False,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> BulkResult[WorkSummary]:
        """Collect a person's credits, with a structured error report."""
        payloads = self._contact_product_payloads(
            extract_numeric_id(id_or_url, kind="contact"),
            self._contact_product_variables(universe, profession, order),
            page_size,
        )
        return await self._collect_items(payloads, parse_work_summary, strict)

    async def search_contacts(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        strict: bool = False,
    ) -> list[ContactSearchHit]:
        """Search people (and companies, labels, studios) by name."""
        data = await self._transport.graphql(
            "SearchContacts",
            CONTACT_SEARCH,
            {"query": query, "limit": limit, "offset": offset},
        )
        explorer = data.get("searchContactExplorer") or {}
        hits: list[ContactSearchHit] = []
        for payload in explorer.get("items") or []:
            try:
                hits.append(parse_contact_search_hit(payload))
            except ParseError as exc:
                if strict:
                    raise
                logger.warning(
                    "skipping malformed contact search result",
                    extra={"query": query, "error": str(exc)},
                )
        return hits
