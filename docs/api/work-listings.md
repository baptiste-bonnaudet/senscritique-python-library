# Product.reviews and Product.shouts

Paginated listings hanging off `product(id:)`. Verified live 2026-07-29.

## Reviews

```graphql
query WorkReviews(
  $id: Int!, $limit: Int!, $offset: Int!,
  $filter: ReviewsFilter, $sortBy: ReviewsSorts
) {
  product(id: $id) {
    reviews(limit: $limit, offset: $offset, filter: $filter, sortBy: $sortBy) {
      total
      items { id title url body bodyText rating dateCreation author { username } }
    }
  }
}
```

- `limit` **and** `offset` are `Int!`: omitting either is a validation error
  (HTTP 400). The handoff-era note that only `offset` is required was wrong.
- `ReviewsFilter`: `NEGATIVE`, `POSITIVE`, `RECOMMEND`, `SCOUT`.
- `ReviewsSorts` (not `ReviewsSortBy`): `DATE_ASC`, `DATE_DESC`,
  `LIKE_POSITIVE_COUNT`.
- `withTopReviews: Boolean` and a `topReviews` result field exist; not
  consumed.
- Items are the same `Review` shape as the root `review(id:)` query
  (`body` is raw markdown-ish source, `bodyText` is rendered HTML).

## Shouts

```graphql
query WorkShouts($id: Int!, $limit: Int, $offset: Int, $order: ShoutsSorts) {
  product(id: $id) {
    shouts(limit: $limit, offset: $offset, order: $order) {
      total
      items { id body rating dateCreation likeCount url author { username } }
    }
  }
}
```

- `ShoutsSorts`: `DATE_ASC`, `DATE_DESC`. All args optional.
- `Shout.rating` may be null (shouts without a rating attached).
- `Shout.url` is an `/activity/{id}` path, not a product path.
- `Shout.author` is non-null with `username`.

## Pagination

Both listings follow the collection pattern: request pages of `limit`
starting at `offset`, advance by the number of items received, stop when a
page is empty or `offset >= total`.
