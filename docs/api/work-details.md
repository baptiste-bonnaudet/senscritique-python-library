# product(id:)

Details for a single work. Found via introspection; verified live 2026-07-29.

## Operation

```graphql
product(id: Int!) -> Product
```

Unknown ids yield `data.product: null` (HTTP 200).

## Consumed response fields

`id`, `title`, `originalTitle`, `yearOfProduction`, `displayedYear`,
`universe` (numeric), `url`, `slug`, `rating`, `synopsis`, `duration`
(seconds), `dateRelease`, `frenchReleaseDate`, `genresInfos { label }`,
`medias { picture backdrop screenshot }`, and the per-universe creator
lists: `directors`, `creators`, `authors`, `developers`, `artists`
(each `{ name }`). The library takes the first non-empty creator list.

Since v0.2 the query also consumes:

- `screenwriters { name }`, `producers { name }` (name lists).
- `actors { name role url person_id }`: main cast; pass
  `actors(fullCasting: true)` for the full list (the library does not).
- `alternativeTitles`: `[String]`.
- `stats { currentCount ratingCount recommendCount reviewCount wishCount }`.
- `statsDetails { split { rating1 .. rating10 } }`: rating histogram, ints.
  `sum(split) == stats.ratingCount` (verified live).
- `similarProducts { <summary fields> }`: observed empty (`[]`) on every
  probe without auth; kept because it is schema-valid and may fill in later.
- `providers { name webUrl providerId }`: JustWatch-style streaming links.
- `vodPlatforms { platform { label } modalities { mode price quality url } }`:
  per-platform rent/buy offers (modes seen: `TVOD`, `VODEST`).
- `numberOfSeasons` (Int, `0` for non-shows), `seasons(limit: Int)`:
  seasons are Products of the unmapped numeric universe **5** with URLs like
  `/serie/breaking_bad/264963/S1`, `yearOfProduction: null`.
- `franchises { id label url }` (URL segment `/groupe/`).

## Example response (trimmed)

```json
{
  "data": {
    "product": {
      "id": 451178,
      "title": "L'Aurore",
      "originalTitle": "Sunrise: A Song of Two Humans",
      "yearOfProduction": 1928,
      "universe": 1,
      "url": "/film/l_aurore/451178",
      "rating": 8.3,
      "duration": 5640,
      "dateRelease": "1927-11-04",
      "genresInfos": [{"label": "Drame"}, {"label": "Romance"}],
      "directors": [{"name": "Friedrich Wilhelm Murnau"}],
      "medias": {"picture": "https://media.senscritique.com/..."},
      "stats": {"ratingCount": 9182}
    }
  }
}
```

## Notes

The `Product` type is much richer than what the library consumes: full
casting (`actors`, `screenwriters`, ...), rating histogram
(`statsDetails`), `similarProducts`, TV seasons/episodes, VOD providers,
ISBN, PEGI, etc. Extend the query in `_queries.py` as tracker needs appear.
