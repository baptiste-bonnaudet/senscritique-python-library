# poll(id:), polls, topPolls, searchPollExplorer

Polls ("tops" voted by users). Verified live 2026-07-29.

## Poll details and works

```graphql
poll(id: Int!) -> Poll
```

Unknown ids: HTTP 200 with `data.poll: null`.

Consumed fields: `id`, `label`, `description`, `url`, `universe` (numeric),
`answersCount` (may be null), `participationCount`, and
`products(limit:, offset:) -> [Product]` for the ranked works.

`products` exposes **no total**; the library paginates until the first page
shorter than `limit`. The root `poll(id:, limit:, offset:)` args mirror the
`products` args.

## Browse and featured

```graphql
polls(universe: String, limit: Int, offset: Int, sortBy: PollSortBy)
  -> Polls { total items [Poll] }
topPolls -> [Poll]
```

`PollSortBy`: `ALL`, `COMPLETE`, `INCOMPLETE`, `NEW`, `NOT_STARTED`
(completion states are per-user and meaningless without auth).

## Poll search

```graphql
query SearchPolls($query: String, $limit: Int, $offset: Int) {
  searchPollExplorer(query: $query, limit: $limit, offset: $offset) {
    total
    items {
      id
      fields { title url universe description cover }
    }
  }
}
```

Items are `TopResultResponse { id fields }` where `fields` is
`TopResultHitFields`. Unlike everywhere else, `fields.universe` is the API
**string** (`"movie"`, `"game"`...), and `url` is absolute
(`/top/resultats/...` paths on www). `sortBy` (`SearchPollExplorerSort`)
exists but is not consumed.
