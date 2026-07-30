"""Pydantic v2 models forming the typed boundary of the library.

Null ratings, years, and dates stay ``None``; they must never leak out as the
string ``"None"``.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Universe(StrEnum):
    """A SensCritique universe (content category).

    Values are the strings the GraphQL API uses. ``numeric_id`` is the id used
    in site URLs (``?universe=N``). Movies and TV are the primary targets;
    ``BOOK`` proves the architecture is not movie-shaped. The remaining
    SensCritique universes are deliberately unmapped for now (see ROADMAP.md).
    """

    MOVIE = "movie"
    TV_SHOW = "tvShow"
    BOOK = "book"

    @property
    def numeric_id(self) -> int:
        return _UNIVERSE_IDS[self]


# Numeric ids as returned by the GraphQL API (Product.universe) and used in
# site URLs (?universe=N). movie=1 and tvShow=4 come from the s2l contract;
# book=2 verified live via searchProductExplorer (2026-07).
_UNIVERSE_IDS: dict[Universe, int] = {
    Universe.MOVIE: 1,
    Universe.BOOK: 2,
    Universe.TV_SHOW: 4,
}


class CollectionAction(StrEnum):
    """User action filter for collection queries (API ``ProductAction``)."""

    CURRENT = "CURRENT"
    DONE = "DONE"
    RATING = "RATING"
    RECENT = "RECENT"
    RECOMMEND = "RECOMMEND"
    SHOPPING_LIST = "SHOPPING_LIST"
    WISH = "WISH"


class CollectionSort(StrEnum):
    """Server-side sort order for collection queries."""

    DATE_RELEASE_DESC = "DATE_RELEASE_DESC"
    LAST_ACTION_DESC = "LAST_ACTION_DESC"
    MY_RATING_DESC = "MY_RATING_DESC"
    POPULARITY_DESC = "POPULARITY_DESC"
    RATING_DESC = "RATING_DESC"
    TITLE_ASC = "TITLE_ASC"
    USER_RATING_DESC = "USER_RATING_DESC"


class ReviewFilter(StrEnum):
    """Server-side filter for a work's reviews listing."""

    NEGATIVE = "NEGATIVE"
    POSITIVE = "POSITIVE"
    RECOMMEND = "RECOMMEND"
    SCOUT = "SCOUT"


class ReviewSort(StrEnum):
    """Sort order for a work's reviews listing."""

    DATE_ASC = "DATE_ASC"
    DATE_DESC = "DATE_DESC"
    LIKE_POSITIVE_COUNT = "LIKE_POSITIVE_COUNT"


class ShoutSort(StrEnum):
    """Sort order for a work's shouts listing."""

    DATE_ASC = "DATE_ASC"
    DATE_DESC = "DATE_DESC"


class WorkSummary(BaseModel):
    """A work (movie, show, book...) as it appears in list responses."""

    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    original_title: str | None = None
    year: int | None = None
    url: str | None = None
    rating: float | None = None
    universe: Universe

    @property
    def display_title(self) -> str:
        """Original title when known, else the (often French) local title."""
        return self.original_title or self.title


class ContactSummary(BaseModel):
    """A person (director, actor, author...) as referenced by works."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    url: str | None = None


class AutocompleteHit(BaseModel):
    """One autocomplete result: a work or a person, never both."""

    model_config = ConfigDict(frozen=True)

    work: WorkSummary | None = None
    contact: ContactSummary | None = None


class UserCollectionItem(BaseModel):
    """One entry of a user's collection: a work plus the user's own data."""

    model_config = ConfigDict(frozen=True)

    work: WorkSummary
    action: CollectionAction
    user_rating: int | None = None
    date_done: datetime.date | None = None
    is_reviewed: bool = False
    review_url: str | None = None


class UserStats(BaseModel):
    """Aggregate counters of a user account."""

    model_config = ConfigDict(frozen=True)

    collection_count: int | None = None
    diary_count: int | None = None
    follower_count: int | None = None
    list_count: int | None = None
    poll_count: int | None = None
    top_count: int | None = None
    rating_count: int | None = None
    review_count: int | None = None
    scout_count: int | None = None


class UserProfile(BaseModel):
    """A user's public profile.

    ``rating_counts``/``wish_counts`` are keyed by the API universe string
    (``"movie"``, ``"game"``...), including universes the library does not
    map as :class:`Universe` members; the ``"total"`` pseudo-universe entry
    is dropped.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    display_name: str | None = None
    url: str | None = None
    description: str | None = None
    date_created: datetime.datetime | None = None
    avatar_url: str | None = None
    backdrop_url: str | None = None
    stats: UserStats | None = None
    rating_counts: dict[str, int] = {}
    wish_counts: dict[str, int] = {}


class UserSearchHit(BaseModel):
    """One result of a user search."""

    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    display_name: str | None = None
    url: str | None = None
    avatar_url: str | None = None
    followers_count: int | None = None
    rating_count: int | None = None


class Review(BaseModel):
    """A user review fetched via the GraphQL ``review(id:)`` query.

    ``body_html`` is the rendered HTML (the API's ``bodyText`` field);
    ``body_raw`` is the author's source text (the API's ``body`` field,
    markdown-flavoured).
    """

    model_config = ConfigDict(frozen=True)

    id: int
    url: str
    title: str | None = None
    body_html: str | None = None
    body_raw: str | None = None
    rating: int | None = None
    author_username: str | None = None
    date_created: datetime.datetime | None = None


class ListSummary(BaseModel):
    """A user-made (or official) list, without its items.

    ``universe_id`` is the API's numeric universe, kept raw because lists
    exist for universes the library does not map.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    label: str
    description: str | None = None
    url: str | None = None
    universe_id: int | None = None
    is_official: bool = False
    is_ordered: bool = False
    is_private: bool = False
    product_count: int | None = None
    author_username: str | None = None
    date_created: datetime.datetime | None = None
    date_last_update: datetime.datetime | None = None


class ListSearchHit(BaseModel):
    """One result of a list search."""

    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    url: str | None = None
    backdrop_url: str | None = None
    like_count: int | None = None
    universe_id: int | None = None
    product_count: int | None = None
    author_username: str | None = None


class ListItem(BaseModel):
    """One entry of a list: a work plus its position and annotation."""

    model_config = ConfigDict(frozen=True)

    work: WorkSummary
    position: int | None = None
    annotation: str | None = None


class PollSummary(BaseModel):
    """A poll ("top" survey), without its ranked works."""

    model_config = ConfigDict(frozen=True)

    id: int
    label: str
    description: str | None = None
    url: str | None = None
    universe_id: int | None = None
    answers_count: int | None = None
    participation_count: int | None = None


class PollSearchHit(BaseModel):
    """One result of a poll search.

    Unlike everywhere else, the search index returns ``universe`` as the API
    string (``"movie"``...), kept as-is.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    url: str | None = None
    universe: str | None = None
    description: str | None = None
    cover_url: str | None = None


class WorkStats(BaseModel):
    """Aggregate user-action counters of a work."""

    model_config = ConfigDict(frozen=True)

    current_count: int | None = None
    rating_count: int | None = None
    recommend_count: int | None = None
    review_count: int | None = None
    wish_count: int | None = None


class RatingHistogram(BaseModel):
    """How many users gave each rating 1..10."""

    model_config = ConfigDict(frozen=True)

    counts: tuple[int, int, int, int, int, int, int, int, int, int]

    def count_for(self, rating: int) -> int:
        """Number of users who rated exactly ``rating`` (1..10)."""
        if not 1 <= rating <= 10:
            raise ValueError(f"rating must be 1..10, got {rating}")
        return self.counts[rating - 1]

    @property
    def total(self) -> int:
        return sum(self.counts)


class CastMember(BaseModel):
    """An actor credit on a work."""

    model_config = ConfigDict(frozen=True)

    name: str
    role: str | None = None
    url: str | None = None
    person_id: int | None = None


class SeasonSummary(BaseModel):
    """One season of a TV show.

    Seasons are API products of the unmapped universe 5 and never appear in
    search, hence a dedicated model without a :class:`Universe` field.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    url: str | None = None
    rating: float | None = None


class Provider(BaseModel):
    """An external streaming provider offering a work (via JustWatch)."""

    model_config = ConfigDict(frozen=True)

    name: str | None = None
    web_url: str
    provider_id: int


class VodOffer(BaseModel):
    """One VOD purchase/rental modality, flattened per platform."""

    model_config = ConfigDict(frozen=True)

    platform: str
    mode: str | None = None
    price: float | None = None
    quality: str | None = None
    url: str | None = None


class Franchise(BaseModel):
    """A franchise/group a work belongs to."""

    model_config = ConfigDict(frozen=True)

    id: int
    label: str | None = None
    url: str | None = None


class ShoutSummary(BaseModel):
    """A short comment ("shout") on a work."""

    model_config = ConfigDict(frozen=True)

    id: int
    body: str | None = None
    rating: int | None = None
    like_count: int | None = None
    url: str | None = None
    author_username: str | None = None
    date_created: datetime.datetime | None = None


class WorkDetails(BaseModel):
    """Detailed information about a single work."""

    model_config = ConfigDict(frozen=True)

    id: int
    title: str
    original_title: str | None = None
    year: int | None = None
    url: str | None = None
    universe: Universe | None = None
    rating: float | None = None
    rating_count: int | None = None
    synopsis: str | None = None
    duration_seconds: int | None = None
    release_date: datetime.date | None = None
    genres: tuple[str, ...] = ()
    creators: tuple[str, ...] = ()
    picture_url: str | None = None
    alternative_titles: tuple[str, ...] = ()
    screenwriters: tuple[str, ...] = ()
    producers: tuple[str, ...] = ()
    cast: tuple[CastMember, ...] = ()
    stats: WorkStats | None = None
    rating_histogram: RatingHistogram | None = None
    similar: tuple[WorkSummary, ...] = ()
    providers: tuple[Provider, ...] = ()
    vod_offers: tuple[VodOffer, ...] = ()
    number_of_seasons: int | None = None
    seasons: tuple[SeasonSummary, ...] = ()
    franchises: tuple[Franchise, ...] = ()
    backdrop_url: str | None = None
    screenshot_url: str | None = None


class TopChartEntry(BaseModel):
    """One ranked entry of a topchart."""

    model_config = ConfigDict(frozen=True)

    position: int
    work: WorkSummary


class BulkError(BaseModel):
    """A single skipped item from a lenient bulk operation."""

    model_config = ConfigDict(frozen=True)

    payload: Any = None
    error_type: str
    message: str


class BulkResult[T](BaseModel):
    """Result of a lenient bulk operation: parsed items plus skipped ones."""

    items: list[T]
    errors: list[BulkError]

    @property
    def ok(self) -> bool:
        return not self.errors
