# searchAutocomplete

Instant-search suggestions mixing works and people. Verified live 2026-07-29.

## Query

```graphql
query Autocomplete($keywords: String!, $limit: Int, $universe: String) {
  searchAutocomplete(keywords: $keywords, limit: $limit, universe: $universe) {
    total
    items {
      product {
        id
        title
        originalTitle
        yearOfProduction
        universe
        url
        slug
        rating
      }
      contact { id name url }
    }
  }
}
```

## Variables

- `keywords` (`String!`): required search text.
- `limit` (`Int`): number of suggestions (the site uses ~10).
- `universe` (`String`): optional universe string filter (`movie`, ...).

## Response shape

`data.searchAutocomplete`:

- `total`: Int.
- `items`: list of `{ product, contact }` where exactly one of the two is
  non-null per item (a work or a person). The library skips items where both
  are null (lenient mode) or raises (`strict=True`).
- `filters`: list of `AutocompleteFilter` (not consumed).

`product` is a regular `Product` (same summary fields as search); `contact`
is a `Contact` (`id`, `name`, `url`, more fields exist, see people docs).

## Notes

- `universe` in `product` is numeric, as everywhere in responses. Hits from
  universes the library does not map yet (see `ROADMAP.md`) are skipped
  leniently like any malformed item.
- Contacts appear regardless of the `universe` filter.
