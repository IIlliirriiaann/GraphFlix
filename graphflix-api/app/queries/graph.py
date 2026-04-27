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
      ELSE coalesce(n.name, 'Actor ' + elementId(n))
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
    sharedGenre: sharedGenre
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
    sharedActor: sharedActor
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

WITH u, focus, collaborativeRows, similarUsers, bridgeMovies, supportMovies, sharedGenres, sharedActors,
     [n IN ([u, focus] + similarUsers + bridgeMovies + supportMovies + sharedGenres + sharedActors) WHERE n IS NOT NULL] AS nodeCandidates

CALL (nodeCandidates) {
  UNWIND nodeCandidates AS n
  WITH DISTINCT n
  RETURN collect(n)[..250] AS limitedNodes
}

WITH u, focus, collaborativeRows, similarUsers, bridgeMovies, supportMovies, sharedGenres, sharedActors, limitedNodes,
     [n IN limitedNodes | elementId(n)] AS limitedNodeIds

WITH [n IN limitedNodes | {
  id: elementId(n),
  label: CASE
    WHEN 'Movie' IN labels(n) THEN coalesce(n.title, 'Movie ' + toString(coalesce(n.movieId, elementId(n))))
    WHEN 'Genre' IN labels(n) THEN coalesce(n.name, 'Unknown genre')
    WHEN 'User' IN labels(n) THEN 'User ' + toString(coalesce(n.userId, elementId(n)))
    ELSE coalesce(n.name, coalesce(n.fullName, 'Actor ' + elementId(n)))
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