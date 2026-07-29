"""Payload-to-model converters.

Each function raises :class:`ParseError` with a payload snippet on unexpected
shapes; callers decide whether to skip (lenient) or propagate (strict).
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import ValidationError

from .errors import ParseError
from .models import (
    CollectionAction,
    Review,
    Universe,
    UserCollectionItem,
    WorkDetails,
    WorkSummary,
)

_ID_BY_NUMBER = {u.numeric_id: u for u in Universe}


def universe_from_number(value: Any) -> Universe:
    """Map the API's numeric universe id to the enum."""
    if isinstance(value, int) and value in _ID_BY_NUMBER:
        return _ID_BY_NUMBER[value]
    raise ParseError(f"unknown universe id: {value!r}", payload=value)


def coerce_universe(value: Universe | str) -> Universe:
    """Accept a Universe or its API string (``"movie"``/``"tvShow"``...)."""
    if isinstance(value, Universe):
        return value
    try:
        return Universe(value)
    except ValueError as exc:
        valid = ", ".join(u.value for u in Universe)
        raise ValueError(
            f"invalid universe {value!r}, expected one of: {valid}"
        ) from exc


def parse_date(value: Any) -> datetime.date | None:
    """ISO date or datetime string to date; None stays None."""
    if value is None:
        return None
    if isinstance(value, str) and len(value) >= 10:
        try:
            return datetime.date.fromisoformat(value[:10])
        except ValueError:
            pass
    raise ParseError(f"unparseable date: {value!r}", payload=value)


def parse_datetime(value: Any) -> datetime.datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    raise ParseError(f"unparseable datetime: {value!r}", payload=value)


def _snippet(payload: Any) -> Any:
    text = repr(payload)
    return text[:300] if len(text) > 300 else payload


def parse_work_summary(payload: dict[str, Any]) -> WorkSummary:
    try:
        return WorkSummary(
            id=payload["id"],
            title=payload["title"],
            original_title=payload.get("originalTitle"),
            year=payload.get("yearOfProduction"),
            url=payload.get("url"),
            rating=payload.get("rating"),
            universe=universe_from_number(payload.get("universe")),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid work payload: {exc}", payload=_snippet(payload)
        ) from exc


def parse_collection_item(
    payload: dict[str, Any], action: CollectionAction
) -> UserCollectionItem:
    work = parse_work_summary(payload)
    infos = payload.get("otherUserInfos") or {}
    try:
        review = infos.get("review") or {}
        return UserCollectionItem(
            work=work,
            action=action,
            user_rating=infos.get("rating"),
            date_done=parse_date(infos.get("dateDone")),
            is_reviewed=bool(infos.get("isReviewed", False)),
            review_url=review.get("url"),
        )
    except (AttributeError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid collection item payload: {exc}", payload=_snippet(payload)
        ) from exc


def _names(payload: dict[str, Any], *keys: str) -> tuple[str, ...]:
    """Collect contact names from the first non-empty of ``keys``."""
    for key in keys:
        contacts = payload.get(key)
        if contacts:
            return tuple(
                c["name"] for c in contacts if isinstance(c, dict) and c.get("name")
            )
    return ()


def parse_work_details(payload: dict[str, Any]) -> WorkDetails:
    try:
        genres = payload.get("genresInfos") or []
        medias = payload.get("medias") or {}
        stats = payload.get("stats") or {}
        return WorkDetails(
            id=payload["id"],
            title=payload["title"],
            original_title=payload.get("originalTitle"),
            year=payload.get("yearOfProduction") or payload.get("displayedYear"),
            url=payload.get("url"),
            universe=universe_from_number(payload.get("universe")),
            rating=payload.get("rating"),
            rating_count=stats.get("ratingCount"),
            synopsis=payload.get("synopsis"),
            duration_seconds=payload.get("duration"),
            release_date=parse_date(
                payload.get("dateRelease") or payload.get("frenchReleaseDate")
            ),
            genres=tuple(
                g["label"] for g in genres if isinstance(g, dict) and g.get("label")
            ),
            creators=_names(
                payload, "directors", "creators", "authors", "developers", "artists"
            ),
            picture_url=medias.get("picture"),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid work details payload: {exc}", payload=_snippet(payload)
        ) from exc


def parse_review(payload: dict[str, Any]) -> Review:
    try:
        author = payload.get("author") or {}
        return Review(
            id=payload["id"],
            url=payload["url"],
            title=payload.get("title"),
            body_html=payload.get("bodyText"),
            body_raw=payload.get("body"),
            rating=payload.get("rating"),
            author_username=author.get("username"),
            date_created=parse_datetime(payload.get("dateCreation")),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid review payload: {exc}", payload=_snippet(payload)
        ) from exc


def extract_numeric_id(value: int | str, *, kind: str) -> int:
    """Accept a numeric id, a numeric string, or a SensCritique URL.

    Work URLs end in the id (``/film/l_aurore/451178``); review URLs end in
    ``/critique/{id}``. Query strings and fragments are stripped.
    """
    if isinstance(value, int):
        return value
    text = value.strip().split("?", 1)[0].split("#", 1)[0].rstrip("/")
    candidate = text.rsplit("/", 1)[-1]
    if candidate.isdigit():
        return int(candidate)
    raise ValueError(f"cannot extract a {kind} id from {value!r}")
