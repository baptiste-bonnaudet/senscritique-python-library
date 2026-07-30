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
  $universe: String, $username: String, $genreId: Int,
  $yearDateDone: Int, $keywords: String, $order: CollectionSort,
  $isAgenda: Boolean
) {
  user(username: $username) {
    collection(
      action: $action, limit: $limit, offset: $offset, universe: $universe,
      genreId: $genreId, yearDateDone: $yearDateDone, keywords: $keywords,
      order: $order, isAgenda: $isAgenda
    ) {
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

_LIST_SUMMARY_FIELDS = """
    id
    label
    description
    url
    universe
    isOfficial
    isOrdered
    isPrivate
    productCount
    dateCreation
    dateLastUpdate
    author { username }
"""

LIST_DETAILS = (
    """
query ListDetails($id: Int!) {
  userList(id: $id) {
"""
    + _LIST_SUMMARY_FIELDS
    + """
  }
}
"""
)

LIST_ITEMS = (
    """
query ListItems($id: Int!, $limit: Int, $offset: Int) {
  userList(id: $id) {
    productsList(limit: $limit, offset: $offset) {
      total
      items {
        position
        annotation
        product {
"""
    + _WORK_SUMMARY_FIELDS
    + """
        }
      }
    }
  }
}
"""
)

LIST_SEARCH = """
query SearchLists($query: String, $limit: Int, $offset: Int) {
  searchListExplorer(query: $query, limit: $limit, offset: $offset) {
    total
    items {
      id
      title
      url
      backdrop
      like_count
      list { universe productCount author { username } }
    }
  }
}
"""

TOP10_LIST = (
    """
query GetTop10($universe: String) {
  getTop10(universe: $universe) {
"""
    + _LIST_SUMMARY_FIELDS
    + """
  }
}
"""
)

_POLL_SUMMARY_FIELDS = """
    id
    label
    description
    url
    universe
    answersCount
    participationCount
"""

POLL_DETAILS = (
    """
query PollDetails($id: Int!) {
  poll(id: $id) {
"""
    + _POLL_SUMMARY_FIELDS
    + """
  }
}
"""
)

POLL_WORKS = (
    """
query PollWorks($id: Int!, $limit: Int, $offset: Int) {
  poll(id: $id) {
    products(limit: $limit, offset: $offset) {
"""
    + _WORK_SUMMARY_FIELDS
    + """
    }
  }
}
"""
)

TOP_POLLS = (
    """
query TopPolls {
  topPolls {
"""
    + _POLL_SUMMARY_FIELDS
    + """
  }
}
"""
)

POLLS = (
    """
query PollsList($universe: String, $limit: Int, $offset: Int, $sortBy: PollSortBy) {
  polls(universe: $universe, limit: $limit, offset: $offset, sortBy: $sortBy) {
    total
    items {
"""
    + _POLL_SUMMARY_FIELDS
    + """
    }
  }
}
"""
)

POLL_SEARCH = """
query SearchPolls($query: String, $limit: Int, $offset: Int) {
  searchPollExplorer(query: $query, limit: $limit, offset: $offset) {
    total
    items {
      id
      fields { title url universe description cover }
    }
  }
}
"""

USER_PROFILE = """
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
"""

USER_SEARCH = """
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
"""

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

GENRES = """
query Genres($universe: String!) {
  genres(universe: $universe) {
    id
    label
  }
}
"""

GENRE_PRODUCTS = (
    """
query GenreProducts(
  $universe: String!, $genre: Int, $order: GenreSort,
  $limit: Int!, $offset: Int!
) {
  genreProducts(
    universe: $universe, genre: $genre, order: $order,
    limit: $limit, offset: $offset
  ) {
    total
    products {
"""
    + _WORK_SUMMARY_FIELDS
    + """
    }
  }
}
"""
)

# ``year`` only narrows the results when paired with byPeriod/period (verified
# live: without them the total stays the whole universe).
PRODUCTS_BY_RELEASE = (
    """
query ProductsByRelease(
  $universe: String!, $year: Int, $byPeriod: Boolean, $period: PeriodSort,
  $sortBy: ProductReleaseSortBy, $limit: Int, $offset: Int
) {
  productsByRelease(
    universe: $universe, year: $year, byPeriod: $byPeriod, period: $period,
    sortBy: $sortBy, limit: $limit, offset: $offset
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

PRODUCTS_BY_MONTH = (
    """
query ProductsByMonth(
  $universe: String!, $year: Int!, $month: Int!, $limit: Int, $offset: Int
) {
  productsByMonth(
    universe: $universe, year: $year, month: $month,
    limit: $limit, offset: $offset
  ) {
"""
    + _WORK_SUMMARY_FIELDS
    + """
  }
}
"""
)

PRODUCTS_BY_WEEK = (
    """
query ProductsByWeek(
  $universe: String!, $year: Int!, $month: Int!, $day: Int!,
  $limit: Int, $offset: Int
) {
  productsByWeek(
    universe: $universe, year: $year, month: $month, day: $day,
    limit: $limit, offset: $offset
  ) {
"""
    + _WORK_SUMMARY_FIELDS
    + """
  }
}
"""
)

GROUP_PRODUCTS = (
    """
query GroupProducts(
  $franchiseId: Int!, $universe: String, $order: GroupSort,
  $limit: Int, $offset: Int
) {
  groupProducts(
    franchiseId: $franchiseId, universe: $universe, order: $order,
    limit: $limit, offset: $offset
  ) {
    items {
"""
    + _WORK_SUMMARY_FIELDS
    + """
    }
  }
}
"""
)

PROVIDERS = """
query Providers {
  providers {
    id
    name
  }
}
"""

STREAMING_EXPLORER = (
    """
query StreamingExplorer(
  $subtype: String!, $providers: [Int], $genres: [Int],
  $yearDateRelease: [Int], $rating: [Int], $countries: [Int],
  $duration: [Int], $onlyPopular: Boolean, $order: StreamingSort,
  $limit: Int, $offset: Int
) {
  streamingExplorer(
    subtype: $subtype, providers: $providers, genres: $genres,
    yearDateRelease: $yearDateRelease, rating: $rating, countries: $countries,
    duration: $duration, onlyPopular: $onlyPopular, order: $order,
    limit: $limit, offset: $offset
  ) {
    total
    products {
"""
    + _WORK_SUMMARY_FIELDS
    + """
    }
  }
}
"""
)

_DISCOVERY_PICK_FIELDS = (
    """
      product {
"""
    + _WORK_SUMMARY_FIELDS
    + """
      }
      similarProduct {
"""
    + _WORK_SUMMARY_FIELDS
    + """
      }
"""
)

DISCOVER_PRODUCTS = (
    """
query DiscoverProducts(
  $universe: String!, $mood: DiscoveryMood, $type: ProductDiscoveryType,
  $excludedProductIds: [Int!]
) {
  discoverProducts(
    universe: $universe, mood: $mood, type: $type,
    excludedProductIds: $excludedProductIds
  ) {
    freshProduct {
"""
    + _DISCOVERY_PICK_FIELDS
    + """
    }
    popularProduct {
"""
    + _DISCOVERY_PICK_FIELDS
    + """
    }
  }
}
"""
)

CONTACT = (
    """
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
    bestProducts {
"""
    + _WORK_SUMMARY_FIELDS
    + """
    }
  }
}
"""
)

CONTACT_PRODUCTS = (
    """
query ContactProducts(
  $id: Int!, $universe: String, $profession: String,
  $order: ContactProductSort, $limit: Int, $offset: Int
) {
  contact(id: $id) {
    productsList(
      universe: $universe, profession: $profession, order: $order,
      limit: $limit, offset: $offset
    ) {
      total
      items {
"""
    + _WORK_SUMMARY_FIELDS
    + """
      }
    }
  }
}
"""
)

CONTACT_SEARCH = """
query SearchContacts($query: String, $limit: Int, $offset: Int) {
  searchContactExplorer(query: $query, limit: $limit, offset: $offset) {
    total
    items {
      id
      name
      url
      picture
      profession
    }
  }
}
"""
