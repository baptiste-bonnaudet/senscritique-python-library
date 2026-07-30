# contact(id:) and searchContactExplorer

People (and companies, labels, studios), which SensCritique calls
"contacts". Verified live 2026-07-29.

## Details

```graphql
query Contact($id: Int!) {
  contact(id: $id) {
    id
    name
    url
    picture
    backdrop
    shortBio
    profession
    nationality
    country
    dateOfBirth
    dateOfDeath
    placeOfBirth
    placeOfDeath
    likeCount
    productCount
    productStats { universe count }
    bestProducts { ...workSummary }
  }
}
```

- `id` is `Int!`; unknown ids return HTTP 200 with `data.contact: null`.
- URLs look like `/contact/{slug}/{id}` (paths, like product urls), and are
  what `searchAutocomplete` and the people search return.
- `profession` is a **list of raw API tags**, reusable verbatim as the
  `profession` filter of `productsList`: observed values include `directors`,
  `actors`, `producers`, `writers`, `authors`, `developers`, `created_by`,
  `artists`, `labels`.
- `dateOfBirth`/`dateOfDeath` are datetimes at **Paris midnight expressed in
  UTC**: Spielberg's 18 December 1946 birthday comes back as
  `1946-12-17T23:00:00.000Z`. Truncating the string to 10 characters is off
  by one day, so the library converts to `Europe/Paris` before taking the
  date.
- `nationality` is a French adjective list (`["Américain"]`), `country` is an
  English country-name list (`["United States of America"]`).
- `productStats` enumerates **every internal universe** (33 entries including
  `notifLikeReview`, `top111`, `badge`...), most of them 0. The library keeps
  the non-zero ones only, keyed by the universe string.
- `bestProducts` mixes universes (movies and tv shows for Spielberg), so
  unmapped-universe entries are dropped from the parsed list.
- Not consumed: `gender` (an undocumented int), `subtypeId` (person vs
  company vs group, values unverified), `isForbidden`, `coworkers`,
  `knownProducts`, `currentProducts`, `futureProducts`, `popularTracks`,
  `lists(universe:)`, `likeUsers`/`likeScouts`, and the per-user
  `currentUserInfos`/`userInfos`.

## Credits (a person's works)

```graphql
contact(id: $id) {
  productsList(
    universe: String, profession: String, order: ContactProductSort,
    albumTypeId: Int, limit: Int, offset: Int
  ) -> Products { total limit offset items [Product] professionCounts }
}
```

- Standard `total` + `items` pagination, nested under `contact`, so an
  unknown id is again a null `contact`.
- `profession` filters by one of the tags above (`"directors"` narrowed
  Spielberg's 215 movie credits to 59).
- `professionCounts` gives `{ tag total universe }` triples across universes
  and is not consumed.
- `ContactProductSort`: `DATE_OF_PRODUCTION_DESC`, `DATE_RELEASE_DESC`,
  `LAST_ACTION_DESC`, `MY_RATING_DESC`, `POPULARITY_DESC`, `RATING_DESC`,
  `SCOUT_RATING_DESC`, `TITLE_ASC`. The three per-user values are
  meaningless without a session.

## People search

```graphql
query SearchContacts($query: String, $limit: Int, $offset: Int) {
  searchContactExplorer(query: $query, limit: $limit, offset: $offset) {
    total
    items { id name url picture profession }
  }
}
```

- Unlike the poll explorer, items are plain `Contact` objects (no
  `TopResultResponse { id fields }` wrapper), so the same field selection as
  `contact(id:)` works.
- Results include non-people contacts: a "murnau" search returns the
  director, an actor namesake, a record label and a brass band.
- `aggregations { identifier count items }` exists (one `type` facet
  observed) and is not consumed.
- `searchContact(keywords!, limit, offset, universe, listId,
  showAlreadyInList) -> SearchContact { results [Contact] total_count
  inListResults }` is a second, older people search over the same data. It
  returned the same three hits in a different order; the library uses the
  explorer variant for parity with product, list, poll and user search.
- `contactSearchResults(query:, filters:, page:)` is a third variant built on
  a SearchKit-style input (`SKFiltersSet`/`SKPageInput`); not consumed.
