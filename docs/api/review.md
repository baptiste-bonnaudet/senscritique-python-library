# review(id:)

Single review fetch. Found via introspection; verified live 2026-07-29.

## Operation

```graphql
review(id: Int!, isPublished: Boolean) -> Review
```

Review ids are the trailing number of review URLs
(`/film/{slug}/critique/{id}`), which is exactly what
`UserCollectionItem.review_url` carries. Unknown ids yield
`data.review: null`.

## Consumed response fields

- `id`, `url`, `title`
- `bodyText`: the **rendered HTML** of the review (`<p>`, `<strong>`,
  `<em>`, links). Mapped to `Review.body_html`.
- `body`: the author's raw source, markdown-flavoured with HTML entities.
  Mapped to `Review.body_raw`.
- `rating` (int or null), `dateCreation` (ISO datetime),
  `author { username }`

## Example response (trimmed)

```json
{
  "data": {
    "review": {
      "id": 7355694,
      "title": "Amour et Désir",
      "url": "/film/l_aurore/critique/7355694",
      "bodyText": "<p>Je viens de regarder le chef-d'oeuvre de <strong><em>Murnau</em></strong>...</p>",
      "rating": 10,
      "dateCreation": "2022-05-05T16:10:33.000Z",
      "author": {"username": "Aurea"}
    }
  }
}
```

## Divergence from the handoff plan

The handoff assumed reviews required scraping the review page HTML with
BeautifulSoup (the s2l approach: `h1[data-testid=review-title]` +
`div[data-testid=review-content]`). The GraphQL root query makes scraping
unnecessary, so the library fetches reviews like every other operation and
`beautifulsoup4` was dropped. Letterboxd-specific HTML massaging
(`<strong>` → `<b>`, `<br>` → newlines, strip `rel`/`target`, bold title
prefix) is an export concern and belongs in the consumer (tracker), operating
on `Review.body_html`.
