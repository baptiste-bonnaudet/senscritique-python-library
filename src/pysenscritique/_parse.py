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
    AutocompleteHit,
    CastMember,
    CollectionAction,
    ContactSummary,
    Franchise,
    Provider,
    RatingHistogram,
    Review,
    SeasonSummary,
    ShoutSummary,
    Universe,
    UserCollectionItem,
    UserProfile,
    UserSearchHit,
    UserStats,
    VodOffer,
    WorkDetails,
    WorkStats,
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


def parse_contact_summary(payload: dict[str, Any]) -> ContactSummary:
    try:
        return ContactSummary(
            id=payload["id"],
            name=payload["name"],
            url=payload.get("url"),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid contact payload: {exc}", payload=_snippet(payload)
        ) from exc


def parse_autocomplete_hit(payload: dict[str, Any]) -> AutocompleteHit:
    product = payload.get("product")
    contact = payload.get("contact")
    if product is None and contact is None:
        raise ParseError(
            "autocomplete item has neither product nor contact",
            payload=_snippet(payload),
        )
    return AutocompleteHit(
        work=parse_work_summary(product) if product is not None else None,
        contact=parse_contact_summary(contact) if contact is not None else None,
    )


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


def _histogram(payload: dict[str, Any]) -> RatingHistogram | None:
    split = (payload.get("statsDetails") or {}).get("split") or {}
    counts = tuple(split.get(f"rating{n}") or 0 for n in range(1, 11))
    if not any(counts):
        return None
    return RatingHistogram(counts=counts)  # type: ignore[arg-type]


def _cast(payload: dict[str, Any]) -> tuple[CastMember, ...]:
    members = []
    for actor in payload.get("actors") or []:
        if isinstance(actor, dict) and actor.get("name"):
            members.append(
                CastMember(
                    name=actor["name"],
                    role=actor.get("role"),
                    url=actor.get("url"),
                    person_id=actor.get("person_id"),
                )
            )
    return tuple(members)


def _similar(payload: dict[str, Any]) -> tuple[WorkSummary, ...]:
    # Auxiliary data: unparseable entries (e.g. unmapped universes) are
    # dropped rather than failing the whole details fetch.
    works = []
    for item in payload.get("similarProducts") or []:
        try:
            works.append(parse_work_summary(item))
        except ParseError:
            continue
    return tuple(works)


def _seasons(payload: dict[str, Any]) -> tuple[SeasonSummary, ...]:
    seasons = []
    for item in payload.get("seasons") or []:
        if isinstance(item, dict) and item.get("id") and item.get("title"):
            seasons.append(
                SeasonSummary(
                    id=item["id"],
                    title=item["title"],
                    url=item.get("url"),
                    rating=item.get("rating"),
                )
            )
    return tuple(seasons)


def _vod_offers(payload: dict[str, Any]) -> tuple[VodOffer, ...]:
    offers = []
    for entry in payload.get("vodPlatforms") or []:
        if not isinstance(entry, dict):
            continue
        label = (entry.get("platform") or {}).get("label")
        if not label:
            continue
        for modality in entry.get("modalities") or []:
            if isinstance(modality, dict):
                offers.append(
                    VodOffer(
                        platform=label,
                        mode=modality.get("mode"),
                        price=modality.get("price"),
                        quality=modality.get("quality"),
                        url=modality.get("url"),
                    )
                )
    return tuple(offers)


def _providers(payload: dict[str, Any]) -> tuple[Provider, ...]:
    providers = []
    for entry in payload.get("providers") or []:
        if isinstance(entry, dict) and entry.get("webUrl") is not None:
            providers.append(
                Provider(
                    name=entry.get("name"),
                    web_url=entry["webUrl"],
                    provider_id=entry.get("providerId") or 0,
                )
            )
    return tuple(providers)


def _franchises(payload: dict[str, Any]) -> tuple[Franchise, ...]:
    return tuple(
        Franchise(id=f["id"], label=f.get("label"), url=f.get("url"))
        for f in payload.get("franchises") or []
        if isinstance(f, dict) and f.get("id") is not None
    )


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
            alternative_titles=tuple(
                t for t in payload.get("alternativeTitles") or [] if t
            ),
            screenwriters=_names(payload, "screenwriters"),
            producers=_names(payload, "producers"),
            cast=_cast(payload),
            stats=WorkStats(
                current_count=stats.get("currentCount"),
                rating_count=stats.get("ratingCount"),
                recommend_count=stats.get("recommendCount"),
                review_count=stats.get("reviewCount"),
                wish_count=stats.get("wishCount"),
            )
            if stats
            else None,
            rating_histogram=_histogram(payload),
            similar=_similar(payload),
            providers=_providers(payload),
            vod_offers=_vod_offers(payload),
            # 0 means "not a show" (movies report 0), not a real count.
            number_of_seasons=payload.get("numberOfSeasons") or None,
            seasons=_seasons(payload),
            franchises=_franchises(payload),
            backdrop_url=medias.get("backdrop"),
            screenshot_url=medias.get("screenshot"),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid work details payload: {exc}", payload=_snippet(payload)
        ) from exc


def _universe_counts(entries: Any) -> dict[str, int]:
    """``[{universe, count}]`` to a dict, dropping the ``total`` pseudo-entry."""
    counts: dict[str, int] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        universe = entry.get("universe")
        if universe and universe != "total":
            counts[universe] = entry.get("count") or 0
    return counts


def parse_user_profile(payload: dict[str, Any]) -> UserProfile:
    try:
        medias = payload.get("medias") or {}
        stats = payload.get("stats") or {}
        return UserProfile(
            id=payload["id"],
            username=payload["username"],
            display_name=payload.get("name"),
            url=payload.get("url"),
            description=payload.get("description"),
            date_created=parse_datetime(payload.get("dateCreation")),
            avatar_url=medias.get("avatar"),
            backdrop_url=medias.get("backdrop"),
            stats=UserStats(
                collection_count=stats.get("collectionCount"),
                diary_count=stats.get("diaryCount"),
                follower_count=stats.get("followerCount"),
                list_count=stats.get("listCount"),
                poll_count=stats.get("pollCount"),
                top_count=stats.get("topCount"),
                rating_count=stats.get("ratingCount"),
                review_count=stats.get("reviewCount"),
                scout_count=stats.get("scoutCount"),
            )
            if stats
            else None,
            rating_counts=_universe_counts(payload.get("ratingCounts")),
            wish_counts=_universe_counts(payload.get("wishCounts")),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid user profile payload: {exc}", payload=_snippet(payload)
        ) from exc


def parse_user_search_hit(payload: dict[str, Any]) -> UserSearchHit:
    try:
        user = payload.get("user") or {}
        username = user.get("username") or payload.get("title")
        if not username:
            raise KeyError("username")
        return UserSearchHit(
            id=payload["id"],
            username=username,
            display_name=payload.get("title"),
            url=payload.get("url"),
            avatar_url=payload.get("avatar"),
            followers_count=payload.get("followers_count"),
            rating_count=payload.get("rating_count"),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid user search payload: {exc}", payload=_snippet(payload)
        ) from exc


def parse_shout(payload: dict[str, Any]) -> ShoutSummary:
    try:
        author = payload.get("author") or {}
        return ShoutSummary(
            id=payload["id"],
            body=payload.get("body"),
            rating=payload.get("rating"),
            like_count=payload.get("likeCount"),
            url=payload.get("url"),
            author_username=author.get("username"),
            date_created=parse_datetime(payload.get("dateCreation")),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ParseError(
            f"invalid shout payload: {exc}", payload=_snippet(payload)
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
