# senscritique2letterboxd (s2l): features and refactor context

Source: `../senscritique2letterboxd/` (PyPI package `s2l`, v0.5.3, GitHub `rx342/senscritique2letterboxd`).

A CLI that exports a SensCritique user's collection (watched movies/TV and watchlist, with ratings, watched dates, and reviews) into CSV files importable by Letterboxd (https://letterboxd.com/import/). Works for private SensCritique profiles because it uses the public GraphQL endpoint, no authentication required.

## Feature list

- **Export watched items** ("DONE" action): title, year, rating out of 10, watched date.
- **Export watchlist** ("WISH" action) via `--watchlist_only`: title, year, rating only (no watched date or review columns).
- **Movies and optionally TV shows** via `--add_tv`: universes `movie` (id 1) and `tvShow` (id 4). Both are fetched with the same code path and concatenated into one result list.
- **Optional review export** via `--add_reviews`: for each rated item flagged `isReviewed`, fetches the review page HTML and converts it to Letterboxd-friendly HTML (keeps `<b>`, converts `<strong>` to `<b>`, `<br>` to double newlines, strips `rel`/`target` from links, prepends the review title in bold).
- **Two input modes**:
  - Flag-based CLI (`--username` required, `parser.error` if missing).
  - Interactive mode (`-i`/`--interactive`) using `questionary` prompts: username, watchlist-only confirm, delay, checkbox for TV shows and reviews.
- **Rate-limit protection**: configurable `--delay` (default 5s) slept between each paginated batch request.
- **Custom user agent**: `--user_agent` (default `Mozilla/5.0`), passed to both the GraphQL POST and the review page fetches.
- **Pagination**: fetches batches with an `offset` until `offset >= total`, with a `rich` progress bar per universe.
- **CSV output** (`--output`, default `output.csv`):
  - Written with `utf-8-sig` encoding (BOM, presumably for Excel).
  - **Split into chunks of 1900 rows** (`output_1.csv`, `output_2.csv`, ...) because Letterboxd's import caps at 1900 movies per file. Single file keeps the original name.
  - Columns are the dict keys of the first row: `Title`, `Year`, `Rating10`, plus `WatchedDate` (DONE only) and `Review` (if requested). These are Letterboxd's expected import column names.
- **Terminal UX** with `rich`: preview table of the 5 last elements (reviews truncated to 70 chars), progress bars, colored done/failure messages.
- **Error handling**: `ValueError` on unknown username (GraphQL returns `user: null`), invalid universe, or invalid action.

## Architecture (current state)

Only two modules:

- `s2l/main.py` (~80 lines): argparse setup, interactive-vs-flags branching, loop over universes, print summary, write CSV.
- `s2l/utils.py` (~500 lines): everything else. Scraping (`get_review`), API client (`get_data_batch`, `get_data`), output (`write_csv`, `pretty_table`), and interactive prompts (`ask_username`, `ask_delay`, `ask_watchlist`, `ask_additional_options`, `get_user_inputs`).

Entry point: `s2l = "s2l.main:main"` in `pyproject.toml`.

### Data flow

1. `main()` resolves config (from flags or interactive prompts) into: `username`, `item_action` ("DONE"/"WISH"), `universes` list, `add_reviews`, `delay`, plus `user_agent` and `output` (always taken from argparse, even in interactive mode).
2. For each universe, `get_data()` paginates `get_data_batch()` with `sleep(delay)` after every batch.
3. `get_data_batch()` POSTs a GraphQL query and maps each product to a flat dict with Letterboxd CSV column names directly (no intermediate domain model).
4. If reviews are requested, each reviewed item triggers a synchronous extra HTTP GET plus BeautifulSoup parse inside the batch loop.
5. `pretty_table()` previews, `write_csv()` writes chunked CSVs.

## SensCritique API details (the valuable reverse-engineering)

This is the hardest-won knowledge in the repo; preserve it in any refactor.

- **Endpoint**: POST to `https://www.senscritique.com/{username}/collection?universe={1|4}` with headers:
  - `Host: apollo.senscritique.com` (the actual GraphQL host, the URL is the referer-shaped public URL)
  - `Content-Type: application/json`, `Accept: application/json`
  - `Referer` set to the same URL
  - `User-Agent` (spoofed browser string)
- **Query**: a large `UserCollection` GraphQL query (operation with ~17 variables), sent as a hand-concatenated JSON string (not `json.dumps` of a dict). Fragments used: `UserMinimal`, `UserNano`, `ProductList`, `ProductUserInfos`, `ProfileStats`. Only a small subset of requested fields is actually consumed.
- **Variables actually used**: `action` ("DONE" or "WISH"), `offset`, `universe` ("movie" or "tvShow" as a string, while the URL query param uses the numeric id), `username`. `limit` is never set, so the server default page size applies (batch size is whatever the server returns; pagination advances by `len(products)`).
- **Fields consumed from the response**:
  - `data.user` null means unknown user.
  - `data.user.collection.total` for pagination and progress.
  - Per product: `originalTitle` (fallback `title`), `yearOfProduction`, `otherUserInfos.rating`, `otherUserInfos.dateDone` (ISO datetime, date part taken by splitting on `"T"`), `otherUserInfos.isReviewed`, `otherUserInfos.review.url`.
- **Review scraping**: GET `https://www.senscritique.com{review_url}`, parse with BeautifulSoup (`html.parser`), title at `h1[data-testid=review-title]`, body at `div[data-testid=review-content]`.
- **Rate limiting exists** on SensCritique's side, hence the default 5s inter-batch delay.

## Letterboxd import constraints encoded in the code

- Max 1900 rows per CSV import file.
- Recognized columns: `Title`, `Year`, `Rating10` (rating on a 10 scale), `WatchedDate` (YYYY-MM-DD), `Review` (HTML allowed, `<b>` works, `<strong>` apparently doesn't, hence the conversion).
- `utf-8-sig` output encoding.

## Tooling and infrastructure

- **Python >= 3.10**, build backend hatchling, managed with `uv` (`uv.lock` committed).
- **Runtime deps**: `requests`, `beautifulsoup4`, `questionary`, `rich`.
- **Dev deps**: `pytest`, `ruff`.
- **Nix packaging**: `default.nix` and `shell.nix` with `npins`-pinned sources; CI checks nix formatting (`nixfmt-tree`/treefmt) and does a `nix-build` smoke test.
- **CI** (GitHub Actions, actions pinned by SHA): ruff check + format check, nix fmt, pytest, then build matrix (`uv sync` + `s2l --help`) across Python 3.10-3.14 on ubuntu, macos-latest, macos-15-intel, plus nix build.
- **Publish workflow**: on `v*.*.*` tags, `uv build` then PyPI trusted publishing (OIDC, environment `pypi`).
- **Dependabot** configured; CODEOWNERS present.

## Known issues, quirks, and tech debt (refactor targets)

- **Tests hit the live SensCritique API** with a real username (`vsv`) and no mocking. They are slow, flaky, network-dependent, and one test (`test_get_data_batch`) puts three calls inside a single `pytest.raises` block, so only the first ever runs. No delay is passed in tests (`get_data` default 5s applies), and full-collection pagination runs in CI.
- **The GraphQL query is a giant hand-built string** spanning ~90 lines, with manual variable interpolation via f-strings (injection-prone if a username contains quotes). Should be a dict passed to `requests.post(json=...)`, and the query trimmed to only the fields consumed.
- **`utils.py` is a grab-bag**: API client, HTML scraping, CSV writing, terminal presentation, and interactive prompts all in one module. Natural split: `api/client`, `scraper/review`, `export/csv`, `cli/prompts`, `cli/display`.
- **No domain model**: rows are `dict[str, str]` keyed by Letterboxd column names from the moment of extraction. Column presence (`WatchedDate`, `Review`) is sniffed from `data[0]` in `pretty_table` and `write_csv`. A dataclass with explicit serialization would remove the `# type: ignore` scattering (8+ occurrences) and the loose `dict[str, object]` return types.
- **Dead/duplicated code**: `get_data_batch` has a duplicated `int_univ` assignment (lines 97-107); `get_data` has a second orphan docstring; imports inside functions (`argparse` in `main`, `urllib`/`bs4` in `get_review`).
- **Mixed HTTP stacks**: `requests` for the GraphQL POST but `urllib.request` for review pages. No shared session, no timeout on either call, no retry/backoff, no HTTP status checking (`json.loads(x.text)` will raise opaquely on a 429/500 HTML body).
- **Rate limiting is naive**: fixed `sleep(delay)` even after the final batch; review fetches inside the batch loop have no delay at all.
- **Interactive mode gaps**: `--output` and `--user_agent` are still taken from argparse defaults (not prompted); config resolution is duplicated between the two branches in `main()`. A single config dataclass resolved once would simplify this.
- **`Rating10` can be the string `"None"`**: `str(x["otherUserInfos"]["rating"])` when rating is null (e.g. watchlist items or unrated watches) produces literal `"None"` in the CSV.
- **`Year` can be `"None"`** the same way if `yearOfProduction` is null.
- **Progress bar edge case**: first batch is fetched before the progress bar exists, so the bar starts already partially complete without showing it.
- **CSV chunking off-by-one smell**: `parts = num_elements // limit` then `range(1, parts + 2)` writes an empty trailing file when `num_elements` is an exact multiple of 1900.
- **Interactive flow asks watchlist and reviews independently**, but reviews are only used for DONE items; asking for reviews with watchlist-only silently does nothing.
- **French-market specifics**: titles prefer `originalTitle` over the (often French) `title`, which is the right call for Letterboxd matching. Keep this behavior.

## Suggestions if refactoring into this repo

- Keep the reverse-engineered GraphQL contract (endpoint, headers, variables, consumed fields) as the core; everything else is replaceable.
- Introduce: a typed config object, a `SensCritiqueClient` (session, timeouts, retries, proper JSON body), a `Film`/`WatchedItem` dataclass, a Letterboxd CSV serializer honoring the 1900-row split and `utf-8-sig`, and a thin CLI layer.
- Replace live-network tests with fixtures (recorded GraphQL responses and review HTML) and keep at most one opt-in integration test.
- Consider `httpx` or `requests.Session` with `Retry`, and per-request rate limiting (including review fetches).
- Normalize null ratings/years/dates to empty strings instead of `"None"`.
