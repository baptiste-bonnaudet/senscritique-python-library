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
    ``BOOK`` proves the architecture is not movie-shaped.
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
    """User action filter for collection queries."""

    DONE = "DONE"
    WISH = "WISH"


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


class UserCollectionItem(BaseModel):
    """One entry of a user's collection: a work plus the user's own data."""

    model_config = ConfigDict(frozen=True)

    work: WorkSummary
    action: CollectionAction
    user_rating: int | None = None
    date_done: datetime.date | None = None
    is_reviewed: bool = False
    review_url: str | None = None


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
