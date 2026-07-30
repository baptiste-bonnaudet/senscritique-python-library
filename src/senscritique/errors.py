"""Exception hierarchy for senscritique.

All library errors derive from :class:`SensCritiqueError` so callers can catch
one base type. The library never calls ``exit()`` and never swallows
exceptions silently.
"""

from __future__ import annotations

from typing import Any


class SensCritiqueError(Exception):
    """Base class for all senscritique errors."""


class TransportError(SensCritiqueError):
    """HTTP-level failure: connection error, timeout, or unexpected status.

    ``status_code`` is set when a response was received, None otherwise.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitedError(TransportError):
    """The server kept returning 429 after all retries were exhausted."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = 429,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after


class GraphQLError(SensCritiqueError):
    """The GraphQL response carried an ``errors`` payload.

    ``errors`` holds the raw error objects from the response body.
    """

    def __init__(self, message: str, *, errors: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.errors = errors


class UserNotFoundError(SensCritiqueError):
    """The requested SensCritique username does not exist."""

    def __init__(self, username: str) -> None:
        super().__init__(f"SensCritique user not found: {username!r}")
        self.username = username


class ParseError(SensCritiqueError):
    """A response body could not be parsed into the expected shape.

    ``payload`` carries a snippet of the offending raw data for debugging.
    """

    def __init__(self, message: str, *, payload: Any = None) -> None:
        super().__init__(message)
        self.payload = payload
