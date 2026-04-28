"""Graph exploration queries for interactive visualization."""

GET_USER_RECOMMENDATION_GRAPH = """
MATCH (u:User {userId: $userId})

CALL (u) {
  RETURN u AS node, 0 AS hop
  UNION
  MATCH p = (u)-[rels*1..3]-(node)
  WHERE ALL(rel IN rels WHERE type(rel) IN ['RATED', 'IN_GENRE', 'ACTED_IN'])
  WITH node, min(length(p)) AS hop
  RETURN node, hop
}

WITH node, min(hop) AS hop
WHERE hop <= $depth
ORDER BY hop ASC,
         CASE
           WHEN 'Movie' IN labels(node) THEN coalesce(node.title, elementId(node))
           WHEN 'Genre' IN labels(node) THEN coalesce(node.name, elementId(node))
           WHEN 'User' IN labels(node) THEN toString(coalesce(node.userId, elementId(node)))
           ELSE coalesce(node.name, elementId(node))
         END ASC
WITH collect(node)[..100] AS limitedNodes
WITH limitedNodes, [n IN limitedNodes | elementId(n)] AS limitedNodeIds

WITH [n IN limitedNodes | {
    id: elementId(n),
    label: CASE
      WHEN 'Movie' IN labels(n) THEN coalesce(n.title, 'Movie ' + toString(coalesce(n.movieId, elementId(n))))
      WHEN 'Genre' IN labels(n) THEN coalesce(n.name, 'Unknown genre')
      WHEN 'User' IN labels(n) THEN 'User ' + toString(coalesce(n.userId, elementId(n)))
      ELSE CASE WHEN n.name IS NOT NULL THEN n.name ELSE 'Actor ' + elementId(n) END
    END,
    type: CASE
      WHEN 'Movie' IN labels(n) THEN 'Movie'
      WHEN 'Genre' IN labels(n) THEN 'Genre'
      WHEN 'User' IN labels(n) THEN 'User'
      ELSE 'Actor'
    END,
    properties: properties(n)
}] AS nodes, limitedNodes, limitedNodeIds

CALL (limitedNodes, limitedNodeIds) {
  UNWIND limitedNodes AS n
  MATCH (n)-[r]-(m)
  WHERE elementId(m) IN limitedNodeIds
    AND type(r) IN ['RATED', 'IN_GENRE', 'ACTED_IN']
  WITH DISTINCT r
  RETURN collect({
    source: elementId(startNode(r)),
    target: elementId(endNode(r)),
    type: type(r),
    weight: CASE
      WHEN type(r) = 'RATED' THEN coalesce(toFloat(r.rating), 1.0)
      ELSE 1.0
    END
  }) AS edges
}

RETURN nodes, edges
"""


GET_RECOMMENDATION_EXPLANATION_GRAPH = """
MATCH (u:User {userId: $userId})
MATCH (focus:Movie {movieId: $movieId})

CALL (u, focus) {
  OPTIONAL MATCH (u)-[ur:RATED]->(common:Movie)<-[sr:RATED]-(sim:User)-[fr:RATED]->(focus)
  WHERE sim <> u
    AND abs(toFloat(coalesce(ur.rating, 0.0)) - toFloat(coalesce(sr.rating, 0.0))) <= 1.0
  WITH sim,
       fr,
       collect(DISTINCT common)[..$maxBridgeMovies] AS commonMovies,
       count(DISTINCT common) AS overlap
  WHERE sim IS NOT NULL AND overlap > 0
  ORDER BY overlap DESC, toFloat(coalesce(fr.rating, 0.0)) DESC
  LIMIT $maxSimilarUsers
  RETURN collect({
    simNode: sim,
    overlap: overlap,
    focusRating: toFloat(coalesce(fr.rating, 0.0)),
    commonMovies: commonMovies
  }) AS collaborativeRows
}

CALL (u, focus) {
  OPTIONAL MATCH (focus)-[:IN_GENRE]-(sharedGenre:Genre)<-[:IN_GENRE]-(support:Movie)<-[ur:RATED]-(u)
  WHERE toFloat(coalesce(ur.rating, 0.0)) >= toFloat($minRating)
  WITH support, sharedGenre, ur
  WHERE support IS NOT NULL AND sharedGenre IS NOT NULL
  ORDER BY toFloat(coalesce(ur.rating, 0.0)) DESC
  RETURN collect(DISTINCT {
    supportMovie: support,
    sharedGenre: sharedGenre,
    userRating: toFloat(coalesce(ur.rating, 0.0))
  })[..$maxSupportMovies] AS genreRows
}

CALL (u, focus) {
  OPTIONAL MATCH (focus)-[faRel]-(sharedActor)<-[saRel]-(support:Movie)<-[ur:RATED]-(u)
  WHERE toFloat(coalesce(ur.rating, 0.0)) >= toFloat($minRating)
    AND type(faRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
    AND type(saRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
  WITH support, sharedActor, ur
  WHERE support IS NOT NULL AND sharedActor IS NOT NULL
  ORDER BY toFloat(coalesce(ur.rating, 0.0)) DESC
  RETURN collect(DISTINCT {
    supportMovie: support,
    sharedActor: sharedActor,
    userRating: toFloat(coalesce(ur.rating, 0.0))
  })[..$maxSupportMovies] AS actorRows
}

WITH u, focus, collaborativeRows, genreRows, actorRows,
     [row IN collaborativeRows | row.simNode] AS similarUserCandidates,
     reduce(allMovies = [], row IN collaborativeRows | allMovies + coalesce(row.commonMovies, [])) AS bridgeMovieCandidates,
     [row IN genreRows | row.supportMovie] + [row IN actorRows | row.supportMovie] AS supportMovieCandidates,
     [row IN genreRows | row.sharedGenre] AS sharedGenreCandidates,
     [row IN actorRows | row.sharedActor] AS sharedActorCandidates

CALL (similarUserCandidates) {
  UNWIND similarUserCandidates AS n
  WITH n WHERE n IS NOT NULL
  RETURN collect(DISTINCT n) AS similarUsers
}

CALL (bridgeMovieCandidates) {
  UNWIND bridgeMovieCandidates AS n
  WITH n WHERE n IS NOT NULL
  RETURN collect(DISTINCT n) AS bridgeMovies
}

CALL (supportMovieCandidates) {
  UNWIND supportMovieCandidates AS n
  WITH n WHERE n IS NOT NULL
  RETURN collect(DISTINCT n) AS supportMovies
}

CALL (sharedGenreCandidates) {
  UNWIND sharedGenreCandidates AS n
  WITH n WHERE n IS NOT NULL
  RETURN collect(DISTINCT n) AS sharedGenres
}

CALL (sharedActorCandidates) {
  UNWIND sharedActorCandidates AS n
  WITH n WHERE n IS NOT NULL
  RETURN collect(DISTINCT n) AS sharedActors
}

WITH u, focus, collaborativeRows, genreRows, actorRows, similarUsers, bridgeMovies, supportMovies, sharedGenres, sharedActors,
     [n IN ([u, focus] + similarUsers + bridgeMovies + supportMovies + sharedGenres + sharedActors) WHERE n IS NOT NULL] AS nodeCandidates

CALL (nodeCandidates) {
  UNWIND nodeCandidates AS n
  WITH DISTINCT n
  RETURN collect(n)[..250] AS limitedNodes
}

WITH u, focus, collaborativeRows, genreRows, actorRows, similarUsers, bridgeMovies, supportMovies, sharedGenres, sharedActors, limitedNodes,
     [n IN limitedNodes | elementId(n)] AS limitedNodeIds

WITH [n IN limitedNodes | {
  id: elementId(n),
  label: CASE
    WHEN 'Movie' IN labels(n) THEN coalesce(n.title, 'Movie ' + toString(coalesce(n.movieId, elementId(n))))
    WHEN 'Genre' IN labels(n) THEN coalesce(n.name, 'Unknown genre')
    WHEN 'User' IN labels(n) THEN 'User ' + toString(coalesce(n.userId, elementId(n)))
    ELSE CASE WHEN n.name IS NOT NULL THEN n.name ELSE 'Actor ' + elementId(n) END
  END,
  type: CASE
    WHEN 'Movie' IN labels(n) THEN 'Movie'
    WHEN 'Genre' IN labels(n) THEN 'Genre'
    WHEN 'User' IN labels(n) THEN 'User'
    ELSE 'Actor'
  END,
  properties: n {
    .*,
    explanationRole: CASE
      WHEN elementId(n) = elementId(focus) THEN 'focus_movie'
      WHEN elementId(n) = elementId(u) THEN 'target_user'
      WHEN n IN similarUsers THEN 'similar_user'
      WHEN n IN bridgeMovies THEN 'bridge_movie'
      WHEN n IN supportMovies THEN 'support_movie'
      WHEN n IN sharedGenres THEN 'shared_genre'
      WHEN n IN sharedActors THEN 'shared_actor'
      ELSE 'context'
    END,
    overlapCount: CASE
      WHEN n IN similarUsers THEN coalesce(head([row IN collaborativeRows WHERE row.simNode = n | toInteger(row.overlap)]), 0)
      ELSE null
    END,
    focusMovieRating: CASE
      WHEN n IN similarUsers THEN coalesce(head([row IN collaborativeRows WHERE row.simNode = n | toFloat(row.focusRating)]), 0.0)
      ELSE null
    END,
    commonBridgeMoviesCount: CASE
      WHEN n IN similarUsers THEN size(coalesce(head([row IN collaborativeRows WHERE row.simNode = n | row.commonMovies]), []))
      ELSE null
    END,
    supportingSimilarUsers: CASE
      WHEN n IN bridgeMovies THEN size([row IN collaborativeRows WHERE n IN coalesce(row.commonMovies, [])])
      ELSE null
    END,
    supportGenreMatches: CASE
      WHEN n IN supportMovies THEN size([row IN genreRows WHERE row.supportMovie = n])
      ELSE null
    END,
    supportActorMatches: CASE
      WHEN n IN supportMovies THEN size([row IN actorRows WHERE row.supportMovie = n])
      ELSE null
    END,
    bestUserRating: CASE
      WHEN n IN supportMovies THEN reduce(
        maxRating = 0.0,
        rating IN (
          [row IN genreRows WHERE row.supportMovie = n | toFloat(coalesce(row.userRating, 0.0))] +
          [row IN actorRows WHERE row.supportMovie = n | toFloat(coalesce(row.userRating, 0.0))]
        ) |
        CASE WHEN rating > maxRating THEN rating ELSE maxRating END
      )
      ELSE null
    END,
    matchedSupportMovieCount: CASE
      WHEN n IN sharedGenres THEN size([row IN genreRows WHERE row.sharedGenre = n])
      WHEN n IN sharedActors THEN size([row IN actorRows WHERE row.sharedActor = n])
      ELSE null
    END,
    similarUserCount: CASE
      WHEN elementId(n) = elementId(focus) THEN size(similarUsers)
      ELSE null
    END,
    bridgeMovieCount: CASE
      WHEN elementId(n) = elementId(focus) THEN size(bridgeMovies)
      ELSE null
    END,
    supportMovieCount: CASE
      WHEN elementId(n) = elementId(focus) OR elementId(n) = elementId(u) THEN size(supportMovies)
      ELSE null
    END,
    sharedGenreCount: CASE
      WHEN elementId(n) = elementId(focus) THEN size(sharedGenres)
      ELSE null
    END,
    sharedActorCount: CASE
      WHEN elementId(n) = elementId(focus) THEN size(sharedActors)
      ELSE null
    END
  }
}] AS nodes,
limitedNodes,
limitedNodeIds,
u,
focus,
collaborativeRows

CALL (limitedNodes, limitedNodeIds) {
  UNWIND limitedNodes AS n
  MATCH (n)-[r]-(m)
  WHERE elementId(m) IN limitedNodeIds
    AND type(r) IN ['RATED', 'IN_GENRE', 'ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR', 'DIRECTED', 'DIRECTED_BY', 'HAS_DIRECTOR']
  WITH DISTINCT r
  RETURN collect({
    source: elementId(startNode(r)),
    target: elementId(endNode(r)),
    type: CASE
      WHEN type(r) IN ['HAS_ACTOR', 'FEATURES_ACTOR'] THEN 'ACTED_IN'
      WHEN type(r) IN ['DIRECTED_BY', 'HAS_DIRECTOR'] THEN 'DIRECTED'
      ELSE type(r)
    END,
    weight: CASE
      WHEN type(r) = 'RATED' THEN coalesce(toFloat(r.rating), 1.0)
      ELSE 1.0
    END
  }) AS relationEdges
}

CALL (u, focus, collaborativeRows) {
  WITH u, focus, [row IN collaborativeRows WHERE row.simNode IS NOT NULL] AS rows
  WITH u,
       focus,
       [row IN rows | {
         source: elementId(u),
         target: elementId(row.simNode),
         type: 'SIMILAR_USER',
         weight: toFloat(row.overlap)
       }] AS simEdges
  RETURN simEdges + [{
    source: elementId(u),
    target: elementId(focus),
    type: 'RECOMMENDED',
    weight: 1.0
  }] AS syntheticEdges
}

WITH nodes, limitedNodeIds, relationEdges, syntheticEdges
WITH nodes,
     [e IN (relationEdges + syntheticEdges)
      WHERE e.source IN limitedNodeIds AND e.target IN limitedNodeIds] AS edges
RETURN nodes, edges
"""