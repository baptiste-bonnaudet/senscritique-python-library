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

_REVIEW_FIELDS = """
    id
    title
    url
    body
    bodyText
    rating
    dateCreation
    author { username }
"""

WORK_DETAILS = (
    """
query WorkDetails($id: Int!, $seasonsLimit: Int) {
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
    screenwriters { name }
    producers { name }
    actors { name role url person_id }
    alternativeTitles
    medias { picture backdrop screenshot }
    stats { currentCount ratingCount recommendCount reviewCount wishCount }
    statsDetails { split {
      rating1 rating2 rating3 rating4 rating5
      rating6 rating7 rating8 rating9 rating10
    } }
    similarProducts {
"""
    + _WORK_SUMMARY_FIELDS
    + """
    }
    providers { name webUrl providerId }
    vodPlatforms { platform { label } modalities { mode price quality url } }
    numberOfSeasons
    seasons(limit: $seasonsLimit) { id title url rating }
    franchises { id label url }
  }
}
"""
)

WORK_REVIEWS = (
    """
query WorkReviews(
  $id: Int!, $limit: Int!, $offset: Int!,
  $filter: ReviewsFilter, $sortBy: ReviewsSorts
) {
  product(id: $id) {
    reviews(limit: $limit, offset: $offset, filter: $filter, sortBy: $sortBy) {
      total
      items {
"""
    + _REVIEW_FIELDS
    + """
      }
    }
  }
}
"""
)

WORK_SHOUTS = """
query WorkShouts($id: Int!, $limit: Int, $offset: Int, $order: ShoutsSorts) {
  product(id: $id) {
    shouts(limit: $limit, offset: $offset, order: $order) {
      total
      items {
        id
        body
        rating
        dateCreation
        likeCount
        url
        author { username }
      }
    }
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

REVIEW = (
    """
query ReviewById($id: Int!) {
  review(id: $id) {
"""
    + _REVIEW_FIELDS
    + """
  }
}
"""
)
