# UserCollection

Paginated read of a user's collection (works plus the user's own data), the
contract originally reverse-engineered by senscritique2letterboxd and still
the backbone of collection sync.

## Operation

`user(username:)` → `collection(action:, limit:, offset:, universe:)`

Variables used by the library:

| Variable   | Type            | Notes                                        |
| ---------- | --------------- | -------------------------------------------- |
| `username` | `String`        | also passed to `otherUserInfos(username:)`   |
| `universe` | `String`        | `movie` / `tvShow` / `book` / ...            |
| `action`   | `ProductAction` | `DONE` (watched/read) or `WISH` (wishlist)   |
| `offset`   | `Int`           | advanced by the number of products returned  |
| `limit`    | `Int`           | page size; the library defaults to 30        |

The library's trimmed query lives in `src/pysenscritique/_queries.py`
(`COLLECTION`). Works even for private profiles.

## Consumed response fields

- `data.user`: `null` means unknown username → `UserNotFoundError`.
- `data.user.collection.total`: drives pagination.
- `data.user.collection.products[]`:
  - `id`, `title`, `originalTitle`, `yearOfProduction`, `universe` (numeric),
    `url`, `slug`, `rating` (community average)
  - `otherUserInfos`: `rating` (user's own, int 1-10 or null), `dateDone`
    (ISO datetime or null), `isReviewed`, `review { id url }`

`total: 0` comes with `products: null` (not an empty list).

## Example response (trimmed)

```json
{
  "data": {
    "user": {
      "collection": {
        "total": 947,
        "products": [
          {
            "id": 498012,
            "title": "Café Lumière",
            "originalTitle": "Kohi jikou",
            "yearOfProduction": 2004,
            "rating": 6.6,
            "slug": "cafe_lumiere",
            "url": "/film/cafe_lumiere/498012",
            "universe": 1,
            "otherUserInfos": {
              "dateDone": null,
              "isReviewed": false,
              "rating": 6,
              "review": null
            }
          }
        ]
      }
    }
  }
}
```

## Known-good full query (reference)

The original s2l query requests far more (user settings, profile stats,
filters, TV agenda, every contact type). If the trimmed query ever breaks,
the full known-good version is in the s2l repo
(`s2l/utils.py`, `get_data_batch`), GitHub `rx342/senscritique2letterboxd`,
and uses fragments `UserMinimal`, `UserNano`, `ProductList`,
`ProductUserInfos`, `ProfileStats`. Richer `ProductUserInfos` fields exist
(`isCurrent`, `isRecommended`, `isRejected`, `numberEpisodeDone`,
`lastEpisodeDone`) if user states beyond DONE/WISH are needed later.
