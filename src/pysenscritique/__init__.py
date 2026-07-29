"""Async Python client library for SensCritique (GraphQL)."""

from importlib.metadata import PackageNotFoundError, version

from ._transport import RateLimit, RetryConfig
from .client import SensCritique
from .errors import (
    GraphQLError,
    ParseError,
    RateLimitedError,
    SensCritiqueError,
    TransportError,
    UserNotFoundError,
)
from .models import (
    AutocompleteHit,
    BulkError,
    BulkResult,
    CastMember,
    CollectionAction,
    CollectionSort,
    ContactSummary,
    Franchise,
    ListItem,
    ListSearchHit,
    ListSummary,
    PollSearchHit,
    PollSummary,
    Provider,
    RatingHistogram,
    Review,
    ReviewFilter,
    ReviewSort,
    SeasonSummary,
    ShoutSort,
    ShoutSummary,
    TopChartEntry,
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
from .sync import SensCritiqueSync

try:
    __version__ = version("pysenscritique")
except PackageNotFoundError:  # pragma: no cover - not installed
    __version__ = "0.0.0"

__all__ = [
    "AutocompleteHit",
    "BulkError",
    "BulkResult",
    "CastMember",
    "CollectionAction",
    "CollectionSort",
    "ContactSummary",
    "Franchise",
    "GraphQLError",
    "ListItem",
    "ListSearchHit",
    "ListSummary",
    "ParseError",
    "PollSearchHit",
    "PollSummary",
    "Provider",
    "RateLimit",
    "RateLimitedError",
    "RatingHistogram",
    "RetryConfig",
    "Review",
    "ReviewFilter",
    "ReviewSort",
    "SeasonSummary",
    "SensCritique",
    "SensCritiqueError",
    "SensCritiqueSync",
    "ShoutSort",
    "ShoutSummary",
    "TopChartEntry",
    "TransportError",
    "Universe",
    "UserCollectionItem",
    "UserNotFoundError",
    "UserProfile",
    "UserSearchHit",
    "UserStats",
    "VodOffer",
    "WorkDetails",
    "WorkStats",
    "WorkSummary",
    "__version__",
]
