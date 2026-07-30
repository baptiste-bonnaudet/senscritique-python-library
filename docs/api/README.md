# SensCritique GraphQL contracts

Reverse-engineered contracts the library depends on. Everything here was
verified live on 2026-07-29 against a handful of rate-limited probes.

## Endpoint

`POST https://apollo.senscritique.com/`

Plain GraphQL over JSON. Headers:

- `Content-Type: application/json`
- `Accept: application/json`
- `User-Agent`: a browser-like string (the library spoofs Chrome on macOS)

No cookies, no auth, no CSRF token needed for any read operation, including
collections of private profiles.

**Divergence from the original s2l contract:** s2l POSTed to
`https://www.senscritique.com/{username}/collection?universe=N` with a spoofed
`Host: apollo.senscritique.com` header. Posting directly to the apollo host
works for every operation and needs no header tricks; the library does that.

## Introspection

Schema introspection is **enabled** on the endpoint (verified 2026-07). If a
contract drifts, re-introspect before guessing:

```graphql
query { __schema { queryType { fields { name } } } }
```

The full query root (94 fields) is easy to dump; see the probe scripts'
approach in git history or re-run an introspection query by hand.

## Error behavior

- GraphQL validation errors return **HTTP 400** with a standard
  `{"errors": [...]}` body.
- Unknown ids (product, review) return HTTP 200 with a `null` data field.
- Unknown usernames return HTTP 200 with `data.user: null`.
- Rate limiting exists server-side; the library defaults to 1 request / 2.5 s.
- Exceeding it trips **Cloudflare**, not the app: HTTP 429 with a JSON body
  carrying `error_code: 1015` / `error_name: "rate_limited"` and a
  `Retry-After` measured in **tens of minutes** (2588 seconds observed on
  2026-07-29 after a burst of unthrottled requests). The block is per IP and
  applies to every operation. `RetryConfig.backoff_max` (30 s) deliberately
  caps the wait, so the transport raises `RateLimitedError` instead of
  sleeping it out; there is nothing to do but wait out the window.

## Universes

`Product.universe` is numeric in responses; query variables and filters use
strings:

| String   | Numeric id | Notes                          |
| -------- | ---------- | ------------------------------ |
| `movie`  | 1          | proven by s2l contract         |
| `book`   | 2          | verified live via search probe |
| `tvShow` | 4          | proven by s2l contract         |

The other SensCritique universes (video games, comics, albums, tracks) exist
in the API but are deliberately not mapped by the library yet; the full
live-verified mapping is recorded in the repo `ROADMAP.md`.

## Operation contracts

- [collection.md](collection.md): `UserCollection` (paginated user collection)
- [search.md](search.md): `searchProductExplorer`
- [autocomplete.md](autocomplete.md): `searchAutocomplete` (works + people)
- [users.md](users.md): `user(username:)`, `searchUserExplorer`
- [work-details.md](work-details.md): `product(id:)`
- [work-listings.md](work-listings.md): `Product.reviews`, `Product.shouts`
- [lists.md](lists.md): `userList(id:)`, `searchListExplorer`, `getTop10`
- [polls.md](polls.md): `poll(id:)`, `polls`, `topPolls`, `searchPollExplorer`
- [topchart.md](topchart.md): `top(universe:, subtype:)`
- [review.md](review.md): `review(id:)`
- [browse.md](browse.md): `genres`, `genreProducts`, `productsByRelease`,
  `productsByMonth`, `productsByWeek`, `groupProducts`, `providers`,
  `streamingExplorer`, `discoverProducts`
- [people.md](people.md): `contact(id:)`, `Contact.productsList`,
  `searchContactExplorer`
