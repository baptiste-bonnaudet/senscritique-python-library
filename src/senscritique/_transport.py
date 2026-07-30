"""HTTP/GraphQL transport: rate limiting, retries, typed errors, logging.

Private module. The GraphQL endpoint is ``https://apollo.senscritique.com/``,
posted to directly (verified live 2026-07: no ``Host`` header spoofing against
``www.senscritique.com`` is needed, unlike the original s2l contract).
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from .errors import (
    GraphQLError,
    ParseError,
    RateLimitedError,
    TransportError,
)
from .logger import build_logger

logger = build_logger("senscritique.transport")

GRAPHQL_URL = "https://apollo.senscritique.com/"
WEB_BASE_URL = "https://www.senscritique.com"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=10.0)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RateLimit:
    """Token-bucket configuration.

    ``min_interval`` is the steady-state seconds between requests (tokens
    refill at 1/min_interval per second); ``burst`` is the bucket capacity.
    A non-positive ``min_interval`` disables rate limiting.
    """

    min_interval: float = 2.5
    burst: int = 1


@dataclass(frozen=True)
class RetryConfig:
    """Exponential backoff configuration for 429/5xx and network errors."""

    max_retries: int = 3
    backoff_base: float = 2.0
    backoff_factor: float = 2.0
    backoff_max: float = 30.0
    jitter: float = 0.5


Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


class _TokenBucket:
    """Async token bucket. Injectable clock/sleep so tests need no real time."""

    def __init__(self, limit: RateLimit, clock: Clock, sleep: Sleep) -> None:
        self._enabled = limit.min_interval > 0
        self._capacity = float(max(1, limit.burst))
        self._fill_rate = 1.0 / limit.min_interval if self._enabled else 0.0
        self._tokens = self._capacity
        self._clock = clock
        self._sleep = sleep
        self._updated = clock()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Take one token, sleeping as needed. Returns seconds waited."""
        if not self._enabled:
            return 0.0
        waited = 0.0
        async with self._lock:
            while True:
                now = self._clock()
                self._tokens = min(
                    self._capacity,
                    self._tokens + (now - self._updated) * self._fill_rate,
                )
                self._updated = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return waited
                wait = (1.0 - self._tokens) / self._fill_rate
                waited += wait
                await self._sleep(wait)


class AsyncTransport:
    """Rate-limited, retrying HTTP transport shared by all operations."""

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        graphql_url: str = GRAPHQL_URL,
        web_base_url: str = WEB_BASE_URL,
        timeout: httpx.Timeout | None = None,
        rate_limit: RateLimit | None = None,
        retry: RetryConfig | None = None,
        client: httpx.AsyncClient | None = None,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.graphql_url = graphql_url
        self.web_base_url = web_base_url
        self._retry = retry if retry is not None else RetryConfig()
        self._bucket = _TokenBucket(
            rate_limit if rate_limit is not None else RateLimit(), clock, sleep
        )
        self._clock = clock
        self._sleep = sleep
        self._rng = rng
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    async def __aenter__(self) -> AsyncTransport:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def graphql(
        self,
        operation: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """POST a GraphQL operation and return the ``data`` payload.

        Variables are always sent as JSON values in the request body, never
        interpolated into the query text.
        """
        # GraphQL validation errors come back as HTTP 400 with an ``errors``
        # body (verified live), so 400 must reach the parsing below instead of
        # raising TransportError.
        response = await self._request(
            "POST",
            self.graphql_url,
            operation=operation,
            json_body={
                "query": query,
                "operationName": operation,
                "variables": variables,
            },
            ok_statuses=frozenset({400}),
        )
        try:
            body: Any = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ParseError(
                f"non-JSON GraphQL response for {operation}",
                payload=response.text[:500],
            ) from exc
        if not isinstance(body, dict):
            raise ParseError(
                f"unexpected GraphQL response shape for {operation}",
                payload=body,
            )
        if body.get("errors"):
            raise GraphQLError(
                f"GraphQL errors for operation {operation}",
                errors=body["errors"],
            )
        if not response.is_success:
            raise TransportError(
                f"GraphQL POST for {operation} failed with HTTP "
                f"{response.status_code}",
                status_code=response.status_code,
            )
        data = body.get("data")
        if not isinstance(data, dict):
            raise ParseError(
                f"GraphQL response for {operation} has no data object",
                payload=body,
            )
        return data

    async def get_text(self, url: str, *, accept: str = "text/html") -> str:
        """Rate-limited GET returning the body text (used for review pages)."""
        response = await self._request("GET", url, accept=accept)
        return response.text

    async def _request(
        self,
        method: str,
        url: str,
        *,
        operation: str | None = None,
        json_body: dict[str, Any] | None = None,
        accept: str | None = None,
        ok_statuses: frozenset[int] = frozenset(),
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if accept is not None:
            headers["Accept"] = accept
        attempt = 0
        while True:
            await self._bucket.acquire()
            start = self._clock()
            error: Exception | None = None
            response: httpx.Response | None = None
            try:
                response = await self._client.request(
                    method, url, json=json_body, headers=headers or None
                )
            except httpx.HTTPError as exc:
                error = exc
            duration_ms = round((self._clock() - start) * 1000, 1)
            status = response.status_code if response is not None else None
            logger.info(
                "http request",
                extra={
                    "method": method,
                    "url": url,
                    "operation": operation,
                    "status": status,
                    "duration_ms": duration_ms,
                    "attempt": attempt,
                },
            )
            if response is not None and not self._is_retryable(response):
                if response.is_success or response.status_code in ok_statuses:
                    return response
                raise TransportError(
                    f"{method} {url} failed with HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            if attempt >= self._retry.max_retries:
                if response is not None and response.status_code == 429:
                    raise RateLimitedError(
                        f"{method} {url} still rate limited after "
                        f"{attempt} retries",
                        retry_after=self._retry_after(response),
                    )
                if response is not None:
                    raise TransportError(
                        f"{method} {url} failed with HTTP "
                        f"{response.status_code} after {attempt} retries",
                        status_code=response.status_code,
                    )
                raise TransportError(
                    f"{method} {url} failed after {attempt} retries: {error}"
                ) from error
            delay = self._backoff_delay(attempt, response)
            logger.warning(
                "retrying request",
                extra={
                    "method": method,
                    "url": url,
                    "operation": operation,
                    "status": status,
                    "attempt": attempt,
                    "delay_s": round(delay, 2),
                },
            )
            await self._sleep(delay)
            attempt += 1

    def _is_retryable(self, response: httpx.Response) -> bool:
        return response.status_code in RETRYABLE_STATUS

    def _backoff_delay(self, attempt: int, response: httpx.Response | None) -> float:
        retry_after = self._retry_after(response) if response is not None else None
        if retry_after is not None:
            return min(retry_after, self._retry.backoff_max)
        delay = self._retry.backoff_base * (self._retry.backoff_factor**attempt)
        delay += self._rng() * self._retry.jitter
        return min(delay, self._retry.backoff_max)

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None
