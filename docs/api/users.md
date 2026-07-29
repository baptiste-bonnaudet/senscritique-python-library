# user(username:) and searchUserExplorer

User profiles and user search. Verified live 2026-07-29.

## Profile

```graphql
query UserProfile($username: String) {
  user(username: $username) {
    id
    username
    name
    url
    description
    dateCreation
    medias { avatar backdrop }
    stats {
      collectionCount diaryCount followerCount listCount pollCount
      topCount ratingCount reviewCount scoutCount
    }
    ratingCounts { universe count }
    wishCounts { universe count }
  }
}
```

- Unknown usernames: HTTP 200 with `data.user: null`.
- `user(id: Int)` also exists as an alternative lookup key (not consumed).
- `dateCreation` is an ISO datetime string.
- `medias(avatarSize:, backdropSize:)` accepts size strings; defaults are
  fine (`120x120` avatar observed).
- `ratingCounts`/`wishCounts` return one `{ universe, count }` entry per
  universe **string** (including universes with count 0) plus a
  `universe: "total"` pseudo-entry that must be skipped when parsing.

## User search

```graphql
query SearchUsers($query: String, $limit: Int, $offset: Int) {
  searchUserExplorer(query: $query, limit: $limit, offset: $offset) {
    total
    items {
      id
      title
      url
      avatar
      followers_count
      rating_count
      user { username }
    }
  }
}
```

- Items are `UserResultHitFields`: `title` is the display name, `url` is
  **absolute** (`https://www.senscritique.com/{username}`, unlike product
  urls which are paths), `subname` exists but was always empty.
- `searchUser(keywords!, limit, mode)` is a distinct, simpler operation
  returning `{ results [User], totalCount }`; the library uses the explorer
  variant for parity with product search.

## versus

`versus(username:, universe:)` compares the **logged-in** user against
`username` (`perfectMatch`, `difference`, `heLikes`... all `[Product]`).
Without auth every field returns null (verified live), so the library does
not expose it; see `ROADMAP.md`.
