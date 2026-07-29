# pysenscritique

Async Python client library for [SensCritique](https://www.senscritique.com),
built on its public GraphQL API. Read-only: collections, search, work
details, topcharts, and reviews. No credentials, no scraping, no persistence.

Movies and TV shows are the primary targets; books are supported to prove the
design is not movie-shaped. Full seven-universe support is the eventual goal.

## Install

Not on PyPI yet; install from the git URL:

```bash
uv add git+https://github.com/baptiste-bonnaudet/pysenscritique
# or
pip install git+https://github.com/baptiste-bonnaudet/pysenscritique
```

Requires Python >= 3.13.

## Quickstart

Async (the core API):

```python
import asyncio
from pysenscritique import SensCritique, Universe

async def main() -> None:
    async with SensCritique() as sc:
        # Paginated collection as an async iterator
        async for item in sc.collection("some_user", Universe.MOVIE):
            print(item.work.display_title, item.user_rating, item.date_done)

        # Or collect everything with a structured error report
        result = await sc.collection_all("some_user", Universe.TV_SHOW)
        print(len(result.items), "items,", len(result.errors), "skipped")

        # Search, details, topcharts, reviews
        works = await sc.search("dune", universe=Universe.MOVIE, limit=5)
        details = await sc.work_details(works[0].id)
        top = await sc.topchart(Universe.MOVIE)  # the "Top 111"
        if result.items and result.items[0].review_url:
            review = await sc.review(result.items[0].review_url)

asyncio.run(main())
```

Sync (thin facade for scripts and the REPL):

```python
from pysenscritique import SensCritiqueSync

with SensCritiqueSync() as sc:
    for work in sc.search("murnau"):
        print(work.display_title, work.year)
```

## Design principles

- **Read-only, zero credentials.** Structured so auth can be added later
  without a rewrite.
- **Pure stateless client.** Typed Pydantic v2 models at the boundary, no
  cache, no storage.
- **Async core** (`httpx.AsyncClient`) with a thin sync facade running on a
  private event loop.
- **Polite by default.** Token-bucket rate limiting (1 request / 2.5 s) across
  all call types, exponential backoff with jitter on 429/5xx, `Retry-After`
  honored. Tune or disable via `RateLimit` and `RetryConfig`:

  ```python
  from pysenscritique import RateLimit, SensCritique

  sc = SensCritique(rate_limit=RateLimit(min_interval=5.0))
  ```

- **Lenient bulk reads.** Malformed items are skipped and reported
  (`BulkResult.errors`), never silently dropped; `strict=True` fails fast.
- **Typed errors.** Everything derives from `SensCritiqueError`:
  `TransportError`, `RateLimitedError`, `GraphQLError`, `UserNotFoundError`,
  `ParseError`.
- **Structured JSON logging**, no print statements.

## API surface

| Method                                             | Returns                          |
| -------------------------------------------------- | -------------------------------- |
| `collection(username, universe, action)`           | async iterator of items          |
| `collection_all(...)`                              | `BulkResult[UserCollectionItem]` |
| `search(query, universe=None, limit=10)`           | `list[WorkSummary]`              |
| `work_details(id_or_url)`                          | `WorkDetails`                    |
| `topchart(universe, subtype="TOP_111")`            | `list[TopChartEntry]`            |
| `review(url_or_id)`                                | `Review`                         |

The GraphQL contracts behind each operation are documented in
[docs/api/](docs/api/README.md).

## Development

```bash
make install           # create venv, install deps (uv)
make check             # ruff + mypy strict + unit tests
make test              # unit tests only (offline, fixture-based)
make test-integration  # live tests against the real API (rate-limited)
```

A weekly canary workflow runs the live suite and opens a pinned issue when
the reverse-engineered contract drifts.

### Dev container

`.devcontainer/` defines an isolated environment with the full toolchain and a
default-deny egress firewall, so agent-driven sessions can run without permission
prompts while confined to this repo and a known set of domains. Open the repo in
VS Code and choose **Reopen in Container**. See
[.devcontainer/README.md](.devcontainer/README.md).

## License

[MIT](./LICENSE)
