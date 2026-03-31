"""Utils queries"""

GET_MOVIE_DETAILS = """
MATCH (m:Movie {movieId: $movieId})
OPTIONAL MATCH (m)-[:IN_GENRE]->(g:Genre)
WITH m, COLLECT(g.name) AS genres
OPTIONAL MATCH (m)<-[r:RATED]-()
RETURN m.movieId AS movieId,
       m.title AS title,
       m.tmdbId AS tmdbId,
       m.imdbId AS imdbId,
       genres,
       AVG(r.rating) AS avgRating,
       COUNT(r) AS numRatings
"""

GET_MOVIES_DETAILS_BY_IDS = """
UNWIND $movieIds AS movieId
MATCH (m:Movie {movieId: movieId})
OPTIONAL MATCH (m)-[:IN_GENRE]->(g:Genre)
WITH m, COLLECT(g.name) AS genres
OPTIONAL MATCH (m)<-[r:RATED]-()
RETURN m.movieId AS movieId,
     m.title AS title,
     m.tmdbId AS tmdbId,
     m.imdbId AS imdbId,
     genres,
     AVG(r.rating) AS avgRating,
     COUNT(r) AS numRatings
"""

GET_TOP_MOVIES_BY_GENRE = """
MATCH (m:Movie)-[:IN_GENRE]->(g:Genre {name: $genre})
MATCH (m)<-[r:RATED]-()
WITH m, AVG(r.rating) AS avgRating, COUNT(r) AS numRatings
WHERE numRatings >= $minRatings
RETURN m.movieId AS movieId,
       m.title AS title,
       avgRating,
       numRatings
ORDER BY avgRating DESC, numRatings DESC
LIMIT $limit
"""

GET_USER_STATS = """
MATCH (u:User {userId: $userId})-[r:RATED]->(m:Movie)
WITH u, r, m
OPTIONAL MATCH (m)-[:IN_GENRE]->(g:Genre)
WITH u, 
     COUNT(DISTINCT m) AS moviesRated,
     AVG(r.rating) AS avgRating,
     COLLECT(DISTINCT g.name) AS genres
RETURN moviesRated,
       avgRating,
       genres,
       SIZE(genres) AS numGenres
"""

GET_USERS = """
MATCH (u:User)
RETURN u.userId AS userId
ORDER BY u.userId
LIMIT $limit
"""