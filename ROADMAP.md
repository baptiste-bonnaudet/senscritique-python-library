# Roadmap

Deferred work, in rough priority order.

## Map all seven universes

The library currently maps only `movie`, `tvShow`, and `book`. Extending the
`Universe` enum to the full set is deliberately deferred until there is a
consumer for it.

The mapping below was verified live on 2026-07-29 (search probes plus an
album `tracklistExtract`), so implementing this is a code change only, no
re-probing needed:

| API string   | Numeric id | URL segment |
| ------------ | ---------- | ----------- |
| `movie`      | 1          | film        |
| `book`       | 2          | livre       |
| `game`       | 3          | jeuvideo    |
| `tvShow`     | 4          | serie       |
| (tv season)  | 5          | serie .../SN |
| `comicBook`  | 6          | bd          |
| `musicAlbum` | 7          | album       |
| `musicTrack` | 8          | morceau     |

Notes:

- Universe 5 is a TV season (items of `Product.seasons`, URLs like
  `/serie/breaking_bad/264963/S1`); it has no known filter string and never
  appears in search. The library models seasons as `SeasonSummary`, without
  a `Universe` member.
- Tracks (`musicTrack`, 8) are absent from the search index: filtering
  `searchProductExplorer` or `searchResult` on `musicTrack` returns nothing
  or a server error. Reach tracks through an album's
  `tracklistExtract { items { ... } }`.
- When implemented: extend `Universe` and `_UNIVERSE_IDS` in `models.py`,
  and unmapped-universe `ParseError` skips (e.g. comics in autocomplete
  results) disappear on their own.

## versus (needs auth)

`versus(username:, universe:)` compares the logged-in user against another
(`perfectMatch`, `difference`, `heLikes`, `wishes`... all product lists).
Verified live 2026-07-29: every field is null without auth, so it is useless
to this credential-free library today. Revisit if auth support ever lands.
