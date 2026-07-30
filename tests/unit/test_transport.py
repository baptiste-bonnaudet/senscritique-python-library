"""Transport behavior: rate limiting, retries, error mapping. No real sleeps."""

from __future__ import annotations

import httpx
import pytest
import respx

from senscritique import (
    GraphQLError,
    ParseError,
    RateLimit,
    RateLimitedError,
    RetryConfig,
    TransportError,
)
from senscritique._transport import GRAPHQL_URL, AsyncTransport, _TokenBucket


class FakeTime:
    """Deterministic clock + sleep recorder; sleeping advances the clock."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_transport(
    fake: FakeTime,
    *,
    rate_limit: RateLimit | None = None,
    retry: RetryConfig | None = None,
) -> AsyncTransport:
    return AsyncTransport(
        rate_limit=rate_limit if rate_limit is not None else RateLimit(min_interval=0),
        retry=retry if retry is not None else RetryConfig(max_retries=2, jitter=0),
        clock=fake.clock,
        sleep=fake.sleep,
        rng=lambda: 0.0,
    )


async def test_token_bucket_spaces_requests() -> None:
    fake = FakeTime()
    bucket = _TokenBucket(RateLimit(min_interval=2.5, burst=1), fake.clock, fake.sleep)
    assert await bucket.acquire() == 0.0
    waited = await bucket.acquire()
    assert waited == pytest.approx(2.5)
    assert fake.sleeps == [pytest.approx(2.5)]


async def test_token_bucket_refills_with_elapsed_time() -> None:
    fake = FakeTime()
    bucket = _TokenBucket(RateLimit(min_interval=2.5, burst=1), fake.clock, fake.sleep)
    await bucket.acquire()
    fake.now += 10.0
    assert await bucket.acquire() == 0.0


async def test_token_bucket_disabled() -> None:
    fake = FakeTime()
    bucket = _TokenBucket(RateLimit(min_interval=0), fake.clock, fake.sleep)
    for _ in range(5):
        assert await bucket.acquire() == 0.0
    assert fake.sleeps == []


@respx.mock
async def test_graphql_success() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"ok": True}})
    async with make_transport(FakeTime()) as transport:
        data = await transport.graphql("Op", "query Op { ok }", {})
    assert data == {"ok": True}


@respx.mock
async def test_graphql_errors_payload() -> None:
    respx.post(GRAPHQL_URL).respond(
        status_code=400,
        json={"errors": [{"message": "Field unknown"}]},
    )
    async with make_transport(FakeTime()) as transport:
        with pytest.raises(GraphQLError) as excinfo:
            await transport.graphql("Op", "query Op { nope }", {})
    assert excinfo.value.errors[0]["message"] == "Field unknown"


@respx.mock
async def test_graphql_non_json_response() -> None:
    respx.post(GRAPHQL_URL).respond(content=b"<html>maintenance</html>")
    async with make_transport(FakeTime()) as transport:
        with pytest.raises(ParseError):
            await transport.graphql("Op", "query Op { ok }", {})


@respx.mock
async def test_non_retryable_http_error() -> None:
    respx.post(GRAPHQL_URL).respond(status_code=404)
    fake = FakeTime()
    async with make_transport(fake) as transport:
        with pytest.raises(TransportError) as excinfo:
            await transport.graphql("Op", "query Op { ok }", {})
    assert excinfo.value.status_code == 404
    assert fake.sleeps == []


@respx.mock
async def test_retry_on_5xx_then_success() -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(502),
        httpx.Response(200, json={"data": {"ok": True}}),
    ]
    fake = FakeTime()
    async with make_transport(fake) as transport:
        data = await transport.graphql("Op", "query Op { ok }", {})
    assert data == {"ok": True}
    # backoff_base * factor**attempt: 2.0 then 4.0
    assert fake.sleeps == [pytest.approx(2.0), pytest.approx(4.0)]


@respx.mock
async def test_rate_limited_after_retries_exhausted() -> None:
    respx.post(GRAPHQL_URL).respond(status_code=429)
    async with make_transport(FakeTime()) as transport:
        with pytest.raises(RateLimitedError):
            await transport.graphql("Op", "query Op { ok }", {})


@respx.mock
async def test_retry_after_header_is_respected() -> None:
    route = respx.post(GRAPHQL_URL)
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json={"data": {"ok": True}}),
    ]
    fake = FakeTime()
    async with make_transport(fake) as transport:
        await transport.graphql("Op", "query Op { ok }", {})
    assert fake.sleeps == [pytest.approx(7.0)]


@respx.mock
async def test_network_error_exhausts_retries() -> None:
    respx.post(GRAPHQL_URL).side_effect = httpx.ConnectError("boom")
    async with make_transport(FakeTime()) as transport:
        with pytest.raises(TransportError, match="boom"):
            await transport.graphql("Op", "query Op { ok }", {})


@respx.mock
async def test_get_text() -> None:
    respx.get("https://www.senscritique.com/page").respond(text="<html>hi</html>")
    async with make_transport(FakeTime()) as transport:
        body = await transport.get_text("https://www.senscritique.com/page")
    assert body == "<html>hi</html>"


@respx.mock
async def test_requests_are_rate_limited() -> None:
    respx.post(GRAPHQL_URL).respond(json={"data": {"ok": True}})
    fake = FakeTime()
    transport = make_transport(fake, rate_limit=RateLimit(min_interval=2.5))
    async with transport:
        await transport.graphql("Op", "query Op { ok }", {})
        await transport.graphql("Op", "query Op { ok }", {})
    assert fake.sleeps == [pytest.approx(2.5)]
