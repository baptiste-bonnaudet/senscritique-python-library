# senscritiquescraper: features and refactor context

Source: `../senscritiquescraper/` (GitHub `dbeley/senscritiquescraper`, v0.3.1, active 2019-2024).

A Python library ("API") to extract data from senscritique.com by scraping HTML pages with BeautifulSoup. Much broader in scope than s2l: it covers all seven SensCritique universes (movies, series, video games, books, comics, albums, tracks) and five page types (user collection, topchart, survey, work list, individual work), plus search.

**Critical caveat: the project is dead.** The README carries a deprecation notice (added June 2024): SensCritique shut down `old.senscritique.com`, the legacy site every URL and CSS selector in this codebase targets. None of the scraping works against the current React/GraphQL site. Its value for a refactor is the feature surface, the domain model, and the lessons, not the selectors. The working extraction path today is the GraphQL approach documented in `SENSCRITIQUE2LETTERBOXD_CONTEXT.md`.

## Feature list (what it could do)

- **User collection export** (`Senscritique.get_user_collection(user)`): every item a user rated, wishlisted, or has in progress, across all universes at once, with pagination. Captured per item: title, URL, original title, year, release date, genre, producer/author, average rating, number of ratings, picture URL, plus collection-specific fields: `User Action` (Rated / Wishlisted / In Progress), `User Rating`, `Recommended` (whether the user "recommends" it).
- **Topchart export** (`get_topchart(url)`): automatically generated rankings (e.g. "Top 111 Films"), category inferred from the URL path segment (`films`, `series`, `jeuxvideo`, `livres`, `bd`, `musique`).
- **Survey export** (`get_survey(url)`): community-voted rankings (e.g. "Les meilleurs films de 2021"), category inferred from the page's active nav item. The code documents the distinction: topcharts are generated, surveys are community-filled, and they use different DOM structures (`elto-item` vs `elpo-item` rows).
- **Work list export** (`get_list_work(url)`): full catalog dumps per genre/subgenre (e.g. all RPG video games, ~6700 rows), paginated.
- **Single work details** (`get_work_details(url)`): rich per-item extraction: title, rating, full rating histogram (1-10 vote counts), year, cover URL, review/vote/favorite/wishlist/in-progress counts, description, and category-specific fields (see schema below).
- **Search** (`get_url(term, rank, genre)` and `get_url_closest_match(term, genre)`): returns the URL of the nth search result, optionally filtered by genre (`Morceaux`, `Albums`, `Films`, `Livres`, `Séries`, `BD`, `Jeux`). The closest-match variant uses `difflib.get_close_matches` against the URL slug, useful for bulk title-to-URL resolution.
- **Helper filename generators**: `create_collection_filename`, `create_topchart_filename`, `create_survey_filename`, `create_list_work_filename`.
- **Example CLI scripts** (`examples/`): six argparse scripts wrapping the library, exporting tab-separated CSVs via pandas with timestamped filenames. Notable pipeline: `scr_get_work_urls.py` (text file of titles to URLs) feeding `scr_get_work_details.py` (URLs to detail CSV).

## Architecture

```
senscritiquescraper/
  Senscritique.py          # public facade, one function per page type
  utils/
    utils.py               # get_soup (requests + lxml), format_number ("1.2K" -> "1200")
    collection_utils.py    # pagination + row dispatch for collections
    topchart_utils.py      # row dispatch for topcharts
    survey_utils.py        # row dispatch for surveys
    list_work_utils.py     # pagination + row dispatch for work lists
    search_utils.py        # search URL building + result extraction
    work_utils.py          # Work class for single-page details
    row_utils/
      row_utils.py         # generic field extractors from a row (title, year, rating, ...)
      movies_utils.py      # per-universe: field dict + column order
      series_utils.py, books_utils.py, comics_utils.py,
      music_utils.py, track_utils.py, videogames_utils.py
```

The layering is the interesting part and held up well over 5 years of site tweaks:

1. **Facade** (`Senscritique.py`): stable public API, one function per use case.
2. **Page-type modules**: know how to find rows and paginate for their page type, then dispatch each row by category.
3. **Per-universe row modules**: declare which fields a universe has, as a dict of field name to generic extractor call, plus a canonical column order for CSV export.
4. **Generic extractors** (`row_utils.py`): one small function per field, each wrapped in try/except returning `None` on failure, so one missing field never kills a row.

Pagination pattern (collections and work lists): read current page number from `span.eipa-current`, build a page-number-to-URL dict from `a.eipa-anchor` links, follow current+1 until absent. `list_work_utils` calls `soup.decompose()` before moving on to bound memory on multi-thousand-page crawls; `collection_utils` doesn't.

## Domain knowledge worth keeping (site-independent)

- **Category vocabulary and mapping**, consistent across the site and still true on the current site:
  - URL work-page segments (singular, French): `film`, `serie`, `jeuvideo`, `livre`, `bd`, `album`, `morceau`.
  - URL section segments (plural): `films`, `series`, `jeuxvideo`, `livres`, `bd`, `musique`.
  - English export names: Movie, Series, Video Game, Book, Comics, Music, Track.
  - s2l's GraphQL confirms the same universes exist as ids (movie=1, tvShow=4), so the numeric mapping for the other five would need rediscovering.
- **Per-universe detail schemas** (from `Work.get_complementary_infos`), i.e. which metadata each universe carries beyond the common set:
  - Movie: Producer, Genre, Length, Release Date
  - Series: Producer, Genre, Season Number, Editor, Episode Length, Release Date
  - Video Game: Developer, Platforms, Genre, Release Date
  - Book: Writer, Genre, Release Date
  - Comics: Writer, Release Date
  - Music: Artist, Genre, Label, Release Date
  - Track: Artist, Length, Release Date
  - Universe quirks: tracks and movies have no "in progress" count; tracks and albums have no description.
- **User-item states**: Rated, Wishlisted, In Progress, plus a separate "Recommended" flag and favorites ("Coups de coeur"). Richer than what s2l exports (DONE/WISH only); the GraphQL `ProductUserInfos` fragment exposes the same states (`isDone`, `isWished`, `isCurrent`, `isRecommended`, `isRejected`).
- **French number formatting**: counts render as "3.8K"; `format_number` converts to "3800".
- **Search genre filter values** are French plural display names, passed as `categories[0][0]` query param.
- **Fuzzy URL matching trick**: SensCritique URL slugs are underscore-separated titles, so `difflib` against `slug.replace("_", " ")` works for title matching. Still applicable to current-site URLs.

## Tooling and infrastructure (dated, 2019-era)

- Packaging: `setup.py` + setuptools, version in `__init__.py`, no PyPI publication. Pipenv (`Pipfile`/`Pipfile.lock`) plus a generated `requirements.txt`. `pyproject.toml` only declares the build backend.
- Deps: `requests`, `beautifulsoup4`, `lxml`, `pandas` (pandas used only in examples yet is an install_requires).
- CI: GitHub Actions on Python 3.8-3.10, flake8 (lenient), pytest with coverage, codecov upload. `bandit.yml`, `codecov.yml`, `.coveragerc` present.
- Tests: extensive by page type and universe (7 work tests, 7 survey tests, 6 topchart tests, collection, list_work, search), but every fixture in `conftest.py` fetches live URLs from `old.senscritique.com`, so the whole suite is dead along with the site. Assertions were value-based against live data (brittle: git history shows repeated "update tests values" commits).

## Lessons for a refactor in this repo

Worth copying:

- **The layered design**: facade / page-type / per-universe field dicts / per-field extractors with graceful None. This structure is why the scraper survived five years of site churn with small patches. It maps cleanly onto a GraphQL client too (per-universe field selections instead of CSS selectors).
- **Field-level fault tolerance**: one function per field, failure yields None and a log line, row survives. Contrast with s2l which would KeyError on an unexpected payload.
- **Explicit column-order declarations** per universe for stable CSV output.
- **Separation of library and CLI**: importable API with thin example scripts, the opposite of s2l where logic lives in the CLI package.
- **Search-based title resolution** (rank-n and closest-match) is a genuinely useful feature neither tool's successor has, and pairs well with a movie-critic use case (resolve a title, fetch details).

Avoid repeating:

- **Scraping HTML CSS classes**: the entire selector layer died with the old site, and the current site's class names are hashed styled-components (`ProductListItem__Container-sc-1ci68b-0` in `search_utils` was already one). The GraphQL API is the durable interface.
- **Live-site test fixtures**: tests should run offline against recorded responses; live checks belong in a small opt-in integration suite.
- **Positional parsing**: `get_complementary_infos` indexes into a list of `<li>` texts by position per category, and `parse_baseline` splits text on `"."`, both extremely brittle (a title or genre containing a period shifts everything).
- **`exit()` inside library code**: `Senscritique.py` calls `exit()` on fetch errors, killing the caller's process. Raise instead.
- **Broad `except Exception` everywhere** with error-level logging even for expected absences (noisy, hides real bugs).
- **Everything is `Optional[str]`**: counts, years, and ratings stay strings ("None" leaks into exports); no domain model, rows are dicts keyed by display-ready English column names from the start.
- **Duplicated pagination code** between `collection_utils` and `list_work_utils` (near-identical functions, one with `decompose()`, one without).
- **No politeness controls**: no delay between page fetches, no timeout, no session reuse, no user-agent header at all (s2l later needed both delays and UA spoofing).

## How the two repos relate

- senscritiquescraper (2019, dbeley): broad read-only scraping of the old HTML site, all universes, library-first. Dead.
- s2l (senscritique2letterboxd): narrow export-to-Letterboxd tool, movies/TV only, but built on the current site's GraphQL endpoint. Alive.
- A refactored movie-critic extraction layer should combine s2l's transport (GraphQL POST, headers, pagination, rate limiting) with senscritiquescraper's architecture (facade, per-universe schemas, field-level tolerance, library/CLI split) and feature ambitions (search, work details, topcharts, richer user states).
