# searchProductExplorer

The current site's main product search (the one behind
`senscritique.com/search`). Found via introspection; verified live 2026-07-29.

## Operation

```graphql
searchProductExplorer(
  query: String, offset: Int, limit: Int,
  filters: [SearchFilter], sortBy: SearchProductExplorerSort,
  infiniteScroll: Boolean
) -> SearchProductExplorerResponse
```

`SearchFilter` input: `{identifier: String!, termValues: [...],
rangeValue: ..., rangeFloatValue: ...}`.

Universe filtering uses `identifier: "universe"` with the universe **string**
in `termValues`:

```json
{
  "query": "dune",
  "offset": 0,
  "limit": 5,
  "filters": [{"identifier": "universe", "termValues": ["movie"]}]
}
```

## Consumed response fields

`data.searchProductExplorer`:

- `total`: total match count
- `items[]`: full `Product` objects; the library reads `id`, `title`,
  `originalTitle`, `yearOfProduction`, `universe` (numeric), `url`, `slug`,
  `rating`

## Notes

- Without a `filters` entry the search spans all universes.
- `aggregations` and `sortOptions` exist on the response for faceting; unused.
- Simpler alternatives exist (`searchResult`, `searchAutocomplete`,
  `searchByUniverse`) but the explorer variant matches the site behavior and
  paginates cleanly with offset/limit.
