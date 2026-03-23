"""Collaborative filtering queries"""

GET_COLLABORATIVE_RECOMMENDATIONS = """
MATCH (target:User {userId: $userId})-[r1:RATED]->(m:Movie)<-[r2:RATED]-(other:User)
WHERE r1.rating >= 4.0 AND r2.rating >= 4.0 AND target <> other
WITH other, COUNT(DISTINCT m) AS commonMovies, target
WHERE commonMovies >= 3

MATCH (other)-[r:RATED]->(rec:Movie)
WHERE NOT EXISTS((target)-[:RATED]->(rec)) AND r.rating >= 4.0
WITH rec, COUNT(DISTINCT other) AS score, AVG(r.rating) AS avgRating
RETURN rec.movieId AS movieId, rec.title AS title, score, avgRating
ORDER BY score DESC, avgRating DESC
LIMIT $limit
"""