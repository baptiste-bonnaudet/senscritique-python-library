# userList(id:), searchListExplorer, getTop10

User lists. Verified live 2026-07-29.

## List details and items

```graphql
userList(id: Int!) -> UserList
```

Unknown ids: HTTP 200 with `data.userList: null`.

Consumed fields: `id`, `label`, `description`, `url`, `universe` (numeric),
`isOfficial`, `isOrdered`, `isPrivate`, `productCount`, `dateCreation`,
`dateLastUpdate`, `author { username }`, and
`productsList(limit:, offset:) -> ListProducts { total items }` where each
item is `ProductListItem { position annotation product }` (`annotation` is
the list author's per-item comment, may be null).

The library splits this into two operations: `ListDetails` (metadata only)
and `ListItems` (paged `productsList` only), paginated via `total`.

`productsList` also takes `sortBy`/`order` args (not consumed).

## listFullItemsMinimal (auth required)

`listFullItemsMinimal(listId: Int!) -> [ItemMinimal { id position title name }]`
errors with `auth/unauthenticated-user` ("Unauthenticated Users Not
Allowed") without a session (verified live). Not exposed; see `ROADMAP.md`.

## List search

```graphql
query SearchLists($query: String, $limit: Int, $offset: Int) {
  searchListExplorer(query: $query, limit: $limit, offset: $offset) {
    total
    items {
      id
      title
      url
      backdrop
      like_count
      list { universe productCount author { username } }
    }
  }
}
```

Item `url` is absolute. `sortBy` (`SearchListExplorerSort`: `RELEVANCE`,
`LAST_ACTION`) and `filters` exist but are not consumed. The nested `list`
field is the full `List` interface if more data is ever needed.

## getTop10

`getTop10(universe: String) -> UserList`: the site's aggregated
"Top 100 films des Tops 10" list (author `senscritique`, `productCount` 0;
items come via `productsList` on the returned id). Same consumed fields as
`userList`.
