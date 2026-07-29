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
    CollectionAction,
    ContactSummary,
    Review,
    TopChartEntry,
    Universe,
    UserCollectionItem,
    WorkDetails,
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
    "CollectionAction",
    "ContactSummary",
    "GraphQLError",
    "ParseError",
    "RateLimit",
    "RateLimitedError",
    "RetryConfig",
    "Review",
    "SensCritique",
    "SensCritiqueError",
    "SensCritiqueSync",
    "TopChartEntry",
    "TransportError",
    "Universe",
    "UserCollectionItem",
    "UserNotFoundError",
    "WorkDetails",
    "WorkSummary",
    "__version__",
]
