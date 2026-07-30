# Browse and discovery

Genre, release, franchise, streaming and discovery listings. Verified live
2026-07-29.

All of these are root query fields returning `Product` lists, so they reuse
the shared work-summary selection (`id title originalTitle yearOfProduction
universe url slug rating`).

## Genres

```graphql
genres(universe: String!) -> [Genres { id label }]
genreProducts(
  universe: String!, genre: Int, order: GenreSort,
  limit: Int!, offset: Int!
) -> GenreProducts { total products [Product] }
```

- `genre` takes the **numeric genre id**, not the label, and ids are
  per-universe (movie "Action" is 8673, tvShow "Action" is 9743). Movies
  return 48 genres, tv shows 44.
- `limit`/`offset` are `Int!` on `genreProducts` (unlike most listings).
- Omitting `genre` browses the whole universe (150 445 movies at the time of
  probing, versus 14 283 for movie/Action).
- `GenreSort`: `DATE_RELEASE_DESC`, `LAST_ACTION_DESC`, `MY_RATING_DESC`,
  `POPULARITY_DESC`, `RATING_DESC`, `TITLE_ASC`. The two per-user values are
  meaningless without a session.
- The same genre ids feed the `genreId` filter of `UserCollection`.

## Releases

```graphql
productsByRelease(
  universe: String!, year: Int, month: Int, day: Int,
  byPeriod: Boolean, period: PeriodSort, sortBy: ProductReleaseSortBy,
  platformType: PlatformType, limit: Int, offset: Int
) -> Products { total limit offset items [Product] }

productsByMonth(
  universe: String!, year: Int!, month: Int!, limit: Int, offset: Int
) -> [Product]

productsByWeek(
  universe: String!, year: Int!, month: Int!, day: Int!,
  limit: Int, offset: Int
) -> [Product]
```

- The month/week variants are named `productsByMonth`/`productsByWeek`, not
  `productsByReleaseMonth`/`Week`, and they return a **bare product list**
  with no total, so pagination stops on the first short page.
- `productsByWeek` is a misnomer: it returns the releases of the **single day**
  `year/month/day`, not of the week containing it. Verified live for June
  2025: day 2 has 1 movie, day 3 none, day 4 five (asking for `limit: 30`
  still returned those five), day 5 two, and the day-2/4/5 result sets are
  disjoint. French releases cluster on Wednesdays, which is why an arbitrary
  date often comes back empty. The library exposes it as
  `products_by_day(year, month, day)`.
- `productsByRelease`'s `year` is ignored unless `byPeriod: true` and
  `period: OUTBYYEAR` accompany it: `year: 2025` alone returned the whole
  universe (total 278 337), with the period pair it returned 1 651. The
  library always sends the three together.
- `PeriodSort`: `OUTBYWEEK`, `OUTBYYEAR`, `OUTOFMONTH`.
- `ProductReleaseSortBy`: `POPULARITY`, `RATING`.
- `PlatformType` (`PS5`, `SWITCH`, `PC`...) only makes sense for the game
  universe and is not consumed.
- `Products` also carries `professionCounts` and `albumTypes` facets, not
  consumed.

## Franchises

```graphql
groupProducts(
  franchiseId: Int!, universe: String, order: GroupSort,
  limit: Int, offset: Int
) -> GroupProducts {
  franchise { id label url }
  totals [{ universe total }]
  limit offset
  items [Product]
}
```

- `franchiseId` is the id exposed as `Product.franchises[].id` by
  `product(id:)` (the `/groupe/{slug}/{id}` URL segment). Dune is 260.
- **No `total` field**: `limit`/`offset` are echoed and pagination stops on
  the first short page. The `totals` list gives per-universe counts instead,
  where `universe: 0` is the all-universes count (78 for Dune, versus 6
  movies and 3 tv shows).
- A franchise spans universes, so an unfiltered walk yields games, albums and
  comics that the library's `Universe` enum does not map; they are skipped
  leniently. Pass `universe` to avoid that.
- `GroupSort`: same six values as `GenreSort`.
- `franchise.url` came back null here even though the work-details
  `franchises` field returns it.

## Streaming

```graphql
providers -> [Provider { id name tablePrefix }]
streamingExplorer(
  subtype: String!, providers: [Int], genres: [Int],
  yearDateRelease: [Int], rating: [Int], duration: [Int], countries: [Int],
  seasons: [Int], lastWeek: Boolean, lastMonth: Boolean,
  onlyWish: Boolean, hideSeen: Boolean, onlyPopular: Boolean,
  order: StreamingSort, limit: Int, offset: Int
) -> StreamingExplorer {
  total
  products [Product]
  filters { providers genres countries period }
  myProviders { id providersIds }
}
```

- `subtype` is **required** and takes a universe string: `"movie"` (14 369
  titles) and `"tvShow"` (7 505) both work.
- Provider ids line up with `Product.providers[].providerId` from work
  details (Netflix 1, Prime Video 2, OCS 3, Canal+ 4, Apple TV+ 6,
  Disney+ 7...). `providers` returns 19 services, of which 18 appear in the
  movie explorer facets.
- `Provider.tablePrefix` duplicated `name` on every row and is not consumed.
- Range filters are `[min, max]` int pairs (`yearDateRelease`, `rating`,
  `duration`, `seasons`).
- `filters` echoes the available facets (providers, genres as
  `{ id name }`, 133 countries, `period { min max }` = 1896..2026). Not
  consumed: `genres(universe:)` and `providers` cover the same ground.
- `myProviders`, `onlyWish` and `hideSeen` are per-user; `myProviders` is
  null without a session.
- `StreamingSort`: `DATE_RELEASE_DESC`, `POPULARITY_DESC`, `RATING_DESC`.
- `activeProviders` and `provider(id:)` also exist; not consumed.

## Discovery

```graphql
discoverProducts(
  universe: String!, mood: DiscoveryMood, type: ProductDiscoveryType,
  excludedProductIds: [Int!], hideSeen: Boolean
) -> ProductDiscoveredResponse {
  freshProduct { product similarProduct }
  popularProduct { product similarProduct }
  wishedProduct { product similarProduct }
  recommendedProduct { product similarProduct }
}
```

- Partially usable without auth: `freshProduct` and `popularProduct` are
  populated, `wishedProduct` and `recommendedProduct` are always null (they
  need a session; see `ROADMAP.md`). The library exposes only the two public
  slots.
- `similarProduct` was null in every draw observed.
- Each call returns a fresh random draw; `excludedProductIds` re-draws
  without works already shown.
- Filtering can empty a slot: `mood: GOOD_VIBES, type: BANGER` returned a
  popular pick but no fresh one.
- `DiscoveryMood`: `AMBIGUOUS`, `ANGRY`, `ANIMALS`, `BAD_VIBES`,
  `CHRISTMAS`, `CRIME`, `ENGAGED`, `ESCAPE`, `FEAR`, `FIGHT`, `FOCUS`,
  `GOOD_VIBES`, `HUMOR`, `KIDS`, `LOVE`, `SUPERHERO`, `TIRED`.
- `ProductDiscoveryType`: `BANGER`, `DUD`, `GUILTY_PLEASURE`, `MID`.
- `discoverProductsMoods` exists as a root field (mood catalogue); not
  consumed since the enum is stable in the schema.
