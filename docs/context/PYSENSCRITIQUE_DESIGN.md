# pysenscritique: design decisions

Scoping session 2026-07-27. The library is the foundation for an MCP server and a local movie/TV tracker (this repo). Goals: reliable, maintainable, secured.

## Decisions

| Topic | Decision |
| --- | --- |
| Name | `pysenscritique`, own repo under `~/src/projects` |
| Repo | Separate from movie-critic; scaffolded with /create-code-project (Python boilerplate + hardened GitHub config) |
| Distribution | GitHub-only for now (git URL / uv source), PyPI later once stable |
| Scope | Movies + TV shows first, but architecture proven against a third universe (e.g. books) so the design isn't movie-shaped. Full seven-universe support is the eventual target |
| Operations | User collection sync, search + work details, reviews, topcharts/browse. All read paths |
| Auth | Read-only v1, no credentials. Client structured so an authenticated session can be added later without a rewrite (auth-ready, not auth-implemented) |
| Boundary | Pure stateless client: typed models + GraphQL transport + rate limiting. No persistence in the lib; the tracker owns storage. Tracker needs are logged in TRACKER_REQUIREMENTS.md as they appear |
| Sync/async | Async core (httpx.AsyncClient), thin sync facade for scripts/REPL. MCP consumes async directly |
| Models | Pydantic v2 at the boundary; payload drift fails loudly. Justified since the MCP SDK pulls pydantic anyway |
| Testing | Offline JSON fixtures for unit/CI tests. Small live canary suite on a weekly GitHub Actions schedule + on demand, to catch SensCritique API drift |
| Rate limiting | Conservative built-in default: token bucket ~1 req/2-3s across all call types (including review fetches), retries with backoff on 429/5xx, configurable by caller |
| Failure policy | Lenient by default on bulk operations: skip malformed items, keep going, return a structured errors list alongside results. `strict=True` flips to fail-fast |
| Pagination API | Async iterator yielding items as pages arrive (progress visible, memory-flat, MCP can stream), plus a `collect_all()` convenience helper |
| Observability | Structured JSON logging by default, using the boilerplate's logger module |
| Canary alerts | On live-canary failure the workflow auto-opens (or updates) a pinned GitHub issue, closes it on recovery |
| Base template | Copy `~/src/boilerplates/python-boilerplate` and use its make targets (`make init name=pysenscritique`, `make check` = ruff + mypy strict + pytest). src layout, uv + hatchling, Python >= 3.13, unit/integration test split |

## Defaults taken without asking (flag if wrong)

- Python >= 3.13 (from the boilerplate).
- MIT license.
- CI with pinned actions per your repo conventions.
- Note: the boilerplate depends on `google-cloud-logging`. For a reusable library that dep looks out of place; plan is to keep the structured-logging module but drop the GCP handler from the lib's runtime deps unless you want it kept.

## Technical foundation (from prior repo analysis)

- Transport: the reverse-engineered GraphQL endpoint documented in SENSCRITIQUE2LETTERBOXD_CONTEXT.md (POST to senscritique.com collection URL with `Host: apollo.senscritique.com`, spoofed UA). Proven working for collection reads, including private profiles. Search, work details, and topcharts need fresh reverse-engineering against the current site's GraphQL (the old scraper's HTML selectors are dead).
- Architecture: layered design from SENSCRITIQUESCRAPER_CONTEXT.md (facade / operation modules / per-universe schemas / field-level fault tolerance), adapted from CSS selectors to GraphQL field selections.
- Anti-goals learned from both repos: no hand-concatenated GraphQL strings (use json= with a variables dict, no f-string injection), no live-site unit tests, no exit() in library code, no "None" strings leaking into exports, no scraping styled-component class names.

## Security posture

- Read-only, zero credential handling in v1.
- No shell-outs, no eval, no dynamic imports; typed inputs validated at the boundary (usernames, URLs) before interpolation into requests.
- GraphQL variables passed as JSON values, never string-interpolated into query text.
- Dependencies minimal and pinned via uv.lock; Dependabot + gitleaks pre-commit per repo conventions.
- Rate limiting on by default so the lib can't accidentally hammer SensCritique from the MCP.
