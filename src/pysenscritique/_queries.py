"""GraphQL query constants.

Trimmed to the fields the library consumes. The full known-good s2l
``UserCollection`` query (the original reverse-engineered contract) is kept in
``docs/api/collection.md`` as the reference. All variables are sent as JSON
values, never interpolated into these strings.
"""

_WORK_SUMMARY_FIELDS = """
    id
    title
    originalTitle
    yearOfProduction
    universe
    url
    slug
    rating
"""

COLLECTION = (
    """
query UserCollection(
  $action: ProductAction, $limit: Int, $offset: Int,
  $universe: String, $username: String
) {
  user(username: $username) {
    collection(action: $action, limit: $limit, offset: $offset, universe: $universe) {
      total
      products {
"""
    + _WORK_SUMMARY_FIELDS
    + """
        otherUserInfos(username: $username) {
          dateDone
          isReviewed
          rating
          review { id url }
        }
      }
    }
  }
}
"""
)

SEARCH = (
    """
query SearchProducts(
  $query: String, $offset: Int, $limit: Int, $filters: [SearchFilter]
) {
  searchProductExplorer(
    query: $query, offset: $offset, limit: $limit, filters: $filters
  ) {
    total
    items {
"""
    + _WORK_SUMMARY_FIELDS
    + """
    }
  }
}
"""
)

AUTOCOMPLETE = (
    """
query Autocomplete($keywords: String!, $limit: Int, $universe: String) {
  searchAutocomplete(keywords: $keywords, limit: $limit, universe: $universe) {
    total
    items {
      product {
"""
    + _WORK_SUMMARY_FIELDS
    + """
      }
      contact { id name url }
    }
  }
}
"""
)

WORK_DETAILS = """
query WorkDetails($id: Int!) {
  product(id: $id) {
    id
    title
    originalTitle
    yearOfProduction
    displayedYear
    universe
    url
    slug
    rating
    synopsis
    duration
    dateRelease
    frenchReleaseDate
    genresInfos { label }
    directors { name }
    creators { name }
    authors { name }
    developers { name }
    artists { name }
    medias { picture }
    stats { ratingCount }
  }
}
"""

TOPCHART = (
    """
query Top($universe: String, $subtype: TopSubtype, $limit: Int, $offset: Int) {
  top(universe: $universe, subtype: $subtype, limit: $limit, offset: $offset) {
"""
    + _WORK_SUMMARY_FIELDS
    + """
  }
}
"""
)

REVIEW = """
query ReviewById($id: Int!) {
  review(id: $id) {
    id
    title
    url
    body
    bodyText
    rating
    dateCreation
    author { username }
  }
}
"""
