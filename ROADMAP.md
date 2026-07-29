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
| `comicBook`  | 6          | bd          |
| `musicAlbum` | 7          | album       |
| `musicTrack` | 8          | morceau     |

Notes:

- There is no universe 5.
- Tracks (`musicTrack`, 8) are absent from the search index: filtering
  `searchProductExplorer` or `searchResult` on `musicTrack` returns nothing
  or a server error. Reach tracks through an album's
  `tracklistExtract { items { ... } }`.
- When implemented: extend `Universe` and `_UNIVERSE_IDS` in `models.py`,
  and unmapped-universe `ParseError` skips (e.g. comics in autocomplete
  results) disappear on their own.
