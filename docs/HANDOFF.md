# Implementation handoff: pysenscritique v0.1

Brief for the implementing agent. Read `CLAUDE.md` and the three docs in `docs/context/` first. This file adds the concrete build plan agreed with Baptiste on 2026-07-27.

## Current state

- Repo scaffolded from Baptiste's python-boilerplate (`make init` already run, package renamed to `pysenscritique`). Local git repo initialized, no commits yet, no GitHub remote. Do NOT create a remote or push; local commits only.
- The boilerplate ships `src/pysenscritique/{config.py,logger.py,__main__.py}`, a Makefile (`make check` = ruff + mypy strict + pytest), Dockerfile, and unit/integration test split.

## Build plan (in order)

### 1. Adapt the scaffold to a library
- pyproject: description "Async Python client library for SensCritique (GraphQL)", runtime deps `httpx`, `pydantic>=2`, keep `python-json-logger`, DROP `google-cloud-logging` (adapt logger.py accordingly, keep structured JSON output). Remove the `[project.scripts]` CLI entry and `__main__.py` (this is a library), remove the Dockerfile and its make target. Add `beautifulsoup4` only if review HTML conversion needs it (it does, see step 5).
- Dev deps: add `pytest-asyncio`, `respx` (httpx mocking). Keep mypy strict.
- Run `make install` then keep `make check` green from the first commit onward.

### 2. Transport layer (`_transport.py` or similar private module)
- `AsyncTransport` wrapping `httpx.AsyncClient` with: base headers (browser-like User-Agent, configurable), timeouts (connect/read, sane defaults ~10s), built-in token-bucket rate limiter (default 1 req / 2.5s, configurable via a `RateLimit` config object), retry with exponential backoff + jitter on 429 and 5xx (respect Retry-After when present, max ~3 retries), and structured logging of each request (method, url, status, duration, retry count).
- GraphQL POST helper: takes operation name, query string constant, variables dict; sends `json={"query": ..., "variables": ...}` to the endpoint with headers `Host: apollo.senscritique.com`, `Content-Type: application/json`, `Accept: application/json`, `Referer` set per the s2l contract (see context doc). Raises typed errors on HTTP failure, non-JSON body, or GraphQL `errors` payload.
- IMPORTANT unknown to verify early: s2l POSTs to `https://www.senscritique.com/{username}/collection?universe=N` with the apollo Host header. Probe whether posting directly to `https://apollo.senscritique.com/` works more cleanly for all operations. Use at most a handful of live requests, spaced out.

### 3. Errors (`errors.py`)
Exception hierarchy: `SensCritiqueError` base; `TransportError`, `RateLimitedError`, `GraphQLError`, `UserNotFoundError`, `ParseError`. Never call exit(), never swallow exceptions silently.

### 4. Models (`models.py`)
Pydantic v2. At minimum: `Universe` (StrEnum: movie, tv_show, book for the architecture-proof, mapping to API strings "movie"/"tvShow"/"book" and numeric ids where needed: movie=1, tvShow=4; discover book's id from filters or probing), `WorkSummary` (id, title, original_title, year, url/slug, rating, universe), `UserCollectionItem` (work + user rating, date_done as `datetime.date | None`, action DONE/WISH, is_reviewed, review_url), `Review`, `WorkDetails`, plus a `BulkResult` generic carrying `items` and `errors` (each error: raw payload snippet + exception info). Null ratings/years stay None, never the string "None".

### 5. Operations
- `collection(username, universe, action, ...)`: async iterator over `UserCollectionItem`, paginating via offset per the s2l contract. Trim the GraphQL query to only needed fields, but keep the full working query from the context doc in a comment or docs file as the known-good reference. `UserNotFoundError` when `data.user` is null.
- `review(review_url)`: fetch and convert review HTML per the s2l rules (title bold, strong to b, br to newlines, strip rel/target). BeautifulSoup, rate-limited like everything else.
- `search(term, universe=None)`: reverse-engineer the current site's GraphQL search operation (probe the site; browser devtools payloads are usually visible in the JS bundle or via the autocomplete endpoint). If GraphQL search cannot be found in reasonable time, ship v0.1 without it and record findings in docs/.
- `work_details(id_or_url)`: same, reverse-engineer the product GraphQL query.
- `topchart(url_or_id)`: same, best effort.
- For each operation reverse-engineered, document the contract (operation name, variables, consumed fields, example response) in `docs/api/` as you go. That documentation is as valuable as the code.

### 6. Facade
`SensCritique` async client class (context-manager) exposing the operations; `SensCritiqueSync` thin wrapper running the async client on an internal event loop. Public API exported from `pysenscritique/__init__.py`.

### 7. Tests
- Unit tests with recorded/handcrafted JSON fixtures under `tests/unit/fixtures/`, using respx to mock httpx. Cover: pagination, lenient vs strict parsing, rate limiter behavior (use a fake clock, no real sleeps), retry/backoff, error mapping, review HTML conversion, model validation edge cases (null rating/year/date).
- Integration tests under `tests/integration/` marked `integration`, hitting the live API for one small public account, skipped by default.
- During development you may run a few live probes to capture real fixture payloads; scrub nothing sensitive (it is public data) but keep fixtures small.

### 8. CI and canary (GitHub Actions, workflows committed but remote comes later)
- `ci.yml`: make check on pushes/PRs (ubuntu, Python 3.13), actions pinned by SHA if convenient, otherwise by version tag.
- `canary.yml`: weekly cron + workflow_dispatch, runs `pytest -m integration`; on failure opens/updates a pinned issue, closes it on recovery (use a maintained action or `gh` scripting).

### 9. Commits
Small conventional commits as you go (scaffold adaptation, transport, models, each operation, tests, CI). `make check` green before each commit. No AI attribution footers.

## Definition of done for v0.1

- `make check` green (ruff, mypy strict, unit tests).
- Collection sync + reviews working end-to-end against fixtures, with the live integration test written (runnable manually).
- Search/work details/topcharts: implemented if reverse-engineering succeeds, otherwise findings documented in `docs/api/` with what was tried.
- README rewritten for the library (install via git URL, quickstart async + sync examples, design principles).
- `docs/api/` contract docs for every live endpoint used.
