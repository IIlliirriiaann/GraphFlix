"""Content-based filtering queries"""

GET_SIMILAR_MOVIES_BY_GENRE = """
MATCH (m:Movie {movieId: $movieId})-[:IN_GENRE]->(g:Genre)<-[:IN_GENRE]-(similar:Movie)
WHERE m <> similar
WITH similar, COLLECT(DISTINCT g.name) AS commonGenres, COUNT(g) AS genreCount
RETURN similar.movieId AS movieId, 
       similar.title AS title,
       commonGenres,
       genreCount
ORDER BY genreCount DESC
LIMIT $limit
"""

GET_USER_CONTENT_RECOMMENDATIONS = """
MATCH (u:User {userId: $userId})-[r:RATED]->(m:Movie)-[:IN_GENRE]->(g:Genre)
WHERE r.rating >= 4.0
WITH u, g, COUNT(m) AS genreScore
ORDER BY genreScore DESC
LIMIT 5

MATCH (g)<-[:IN_GENRE]-(rec:Movie)
WHERE NOT EXISTS((u)-[:RATED]->(rec))
WITH rec, SUM(genreScore) AS totalScore
RETURN rec.movieId AS movieId,
       rec.title AS title,
       totalScore
ORDER BY totalScore DESC
LIMIT $limit
"""