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
`medias { picture }`, `stats { ratingCount }`, and the per-universe creator
lists: `directors`, `creators`, `authors`, `developers`, `artists`
(each `{ name }`). The library takes the first non-empty creator list.

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
