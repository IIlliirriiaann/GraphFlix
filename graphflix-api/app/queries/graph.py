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