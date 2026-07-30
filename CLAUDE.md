# senscritique-python-library

Async Python client library for SensCritique (senscritique.com), built on its GraphQL API. Read-only. Powers an MCP server and a local movie/TV tracker (repo `../movie-critic`).

## Context documents (read before significant work)

- `docs/context/SENSCRITIQUE_PYTHON_LIBRARY_DESIGN.md`: all design decisions (scope, auth, models, testing, rate limiting). Authoritative.
- `docs/context/SENSCRITIQUE2LETTERBOXD_CONTEXT.md`: the reverse-engineered GraphQL contract that is proven to work (endpoint, headers, variables, consumed fields).
- `docs/context/SENSCRITIQUESCRAPER_CONTEXT.md`: architecture lessons and SensCritique domain knowledge from a prior (dead) scraper.

## Non-negotiable design rules

- Read-only, zero credential handling. Structure the client so auth can be added later without a rewrite.
- Pure stateless client: no persistence, no cache layers. Tracker requirements get logged in `../movie-critic/TRACKER_REQUIREMENTS.md`, not implemented here.
- Async core (httpx.AsyncClient), thin sync facade. Pydantic v2 models at the boundary.
- GraphQL variables passed as JSON values (`json=` body), never string-interpolated into query text.
- Rate limiting on by default: token bucket ~1 request per 2.5s across all call types, exponential backoff on 429/5xx, configurable.
- Bulk operations are lenient by default (skip bad items, collect them in a structured error report); `strict=True` fails fast.
- Paginated data is exposed as async iterators; `collect_all()` helpers for convenience.
- Structured JSON logging via the project logger module. No print statements in library code.
- Tests: offline JSON fixtures for unit tests (`tests/unit`), live tests only under `tests/integration` marked `integration`, never run in default CI.

## Commands

- `make install`: create venv and install deps (uv)
- `make check`: ruff lint + mypy strict + unit tests. Must pass before any commit.
- `make test`: unit tests only

## Conventions

- When probing the live SensCritique API during development: keep it to a handful of requests, always with delays, always with the spoofed browser User-Agent.
