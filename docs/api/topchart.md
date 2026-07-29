# top(universe:, subtype:)

Generated topcharts (the site's "Top 111" pages). Found via introspection;
verified live 2026-07-29.

## Operation

```graphql
top(limit: Int, offset: Int, subtype: TopSubtype, universe: String) -> [Product]
```

`TopSubtype` enum values (from introspection):

- `TOP_111`: the main per-universe top
- `TOP_111_ANIME`
- `TOP_100_OUT_OF_TOP_10`

## Consumed response fields

`data.top[]` is a ranked list of `Product` objects (order = rank). The
library reads the same summary fields as search and assigns
`position = offset + index + 1`.

## Notes

- The library exposes this as `topchart(universe, subtype=...)` rather than
  the handoff's `topchart(url_or_id)`: the API addresses charts by
  universe + subtype, not by id, and chart URLs don't embed a numeric id.
- Community "surveys" (polls) are a different family
  (`topPolls`, `searchPollExplorer`, `pollAnswerContainsProduct`); not
  implemented in v0.1.
- `getTop10(universe:)` returns the small editorial top-10 list; unused.
