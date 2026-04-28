"""Content-based filtering queries"""

GET_SIMILAR_MOVIES_BY_GENRE = """
/*
Algorithm: Content similarity with weighted Jaccard signals.

Parameters:
- $movieId (int): reference movie
- $limit (int): max returned similar movies

Scoring:
- genreJaccard = |genres intersection| / |genres union|
- actorJaccard = |actors intersection| / |actors union| (if actor edges exist)
- directorJaccard = |directors intersection| / |directors union| (if director edges exist)
- rawScore = 0.6*genreJaccard + 0.3*actorJaccard + 0.1*directorJaccard
- score in [0,1] by min-max normalization blended with z-score logistic normalization

Performance notes:
- Uses set-based list operations to avoid repeated candidate expansion
- Actor/director matches are optional and schema-tolerant

Example output row:
{
  movieId: 593,
  title: "Silence of the Lambs, The (1991)",
  score: 0.7442,
  explanation: {
    matchedGenres: ["Crime", "Thriller"],
    matchedActors: ["Jodie Foster"],
    matchedDirectors: [],
    componentScores: {genreJaccard: 0.5, actorJaccard: 0.2, directorJaccard: 0.0}
  }
}
*/
MATCH (m:Movie {movieId: $movieId})
OPTIONAL MATCH (m)-[:IN_GENRE]->(g:Genre)
WITH m, COLLECT(DISTINCT g.name) AS targetGenres
OPTIONAL MATCH (m)-[ma]-(a)
WHERE type(ma) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH m, targetGenres,
  COLLECT(DISTINCT CASE WHEN a.name IS NOT NULL THEN a.name ELSE toString(elementId(a)) END) AS targetActors
OPTIONAL MATCH (m)-[md]-(d)
WHERE type(md) IN ['DIRECTED', 'DIRECTED_BY', 'HAS_DIRECTOR']
WITH m, targetGenres, targetActors,
  COLLECT(DISTINCT CASE WHEN d.name IS NOT NULL THEN d.name ELSE toString(elementId(d)) END) AS targetDirectors

MATCH (similar:Movie)
WHERE similar <> m
OPTIONAL MATCH (similar)-[:IN_GENRE]->(sg:Genre)
WITH similar, targetGenres, targetActors, targetDirectors,
     COLLECT(DISTINCT sg.name) AS similarGenres
OPTIONAL MATCH (similar)-[saRel]-(sa)
WHERE type(saRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH similar, targetGenres, targetActors, targetDirectors, similarGenres,
  COLLECT(DISTINCT CASE WHEN sa.name IS NOT NULL THEN sa.name ELSE toString(elementId(sa)) END) AS similarActors
OPTIONAL MATCH (similar)-[sdRel]-(sd)
WHERE type(sdRel) IN ['DIRECTED', 'DIRECTED_BY', 'HAS_DIRECTOR']
WITH similar, targetGenres, targetActors, targetDirectors,
     similarGenres, similarActors,
  COLLECT(DISTINCT CASE WHEN sd.name IS NOT NULL THEN sd.name ELSE toString(elementId(sd)) END) AS similarDirectors

WITH similar,
     [gName IN targetGenres WHERE gName IN similarGenres] AS matchedGenres,
     [actorName IN targetActors WHERE actorName IN similarActors] AS matchedActors,
     [directorName IN targetDirectors WHERE directorName IN similarDirectors] AS matchedDirectors,
     (SIZE(targetGenres) + SIZE(similarGenres) - SIZE([gName IN targetGenres WHERE gName IN similarGenres])) AS genreUnion,
     (SIZE(targetActors) + SIZE(similarActors) - SIZE([actorName IN targetActors WHERE actorName IN similarActors])) AS actorUnion,
     (SIZE(targetDirectors) + SIZE(similarDirectors) - SIZE([directorName IN targetDirectors WHERE directorName IN similarDirectors])) AS directorUnion
WITH similar,
     matchedGenres,
     matchedActors,
     matchedDirectors,
     CASE WHEN genreUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedGenres)) / toFloat(genreUnion) END AS genreJaccard,
     CASE WHEN actorUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedActors)) / toFloat(actorUnion) END AS actorJaccard,
     CASE WHEN directorUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedDirectors)) / toFloat(directorUnion) END AS directorJaccard
WITH similar,
     matchedGenres,
     matchedActors,
     matchedDirectors,
     genreJaccard,
     actorJaccard,
     directorJaccard,
     (0.6 * genreJaccard + 0.3 * actorJaccard + 0.1 * directorJaccard) AS rawScore
WHERE rawScore > 0.0

WITH COLLECT({
    movieId: similar.movieId,
    title: similar.title,
    matchedGenres: matchedGenres,
    matchedActors: matchedActors,
    matchedDirectors: matchedDirectors,
    genreJaccard: genreJaccard,
    actorJaccard: actorJaccard,
    directorJaccard: directorJaccard,
    rawScore: rawScore
}) AS rows
WITH rows,
     SIZE(rows) AS rowCount,
     REDUCE(minScore = 1.0, row IN rows | CASE WHEN row.rawScore < minScore THEN row.rawScore ELSE minScore END) AS minScore,
     REDUCE(maxScore = 0.0, row IN rows | CASE WHEN row.rawScore > maxScore THEN row.rawScore ELSE maxScore END) AS maxScore,
     REDUCE(total = 0.0, row IN rows | total + row.rawScore) AS totalScore
WITH rows, rowCount, minScore, maxScore,
     CASE WHEN rowCount = 0 THEN 0.0 ELSE totalScore / toFloat(rowCount) END AS meanScore
WITH rows, rowCount, minScore, maxScore, meanScore,
     CASE
       WHEN rowCount = 0 THEN 0.0
       ELSE sqrt(REDUCE(varAcc = 0.0, row IN rows | varAcc + (row.rawScore - meanScore) * (row.rawScore - meanScore)) / toFloat(rowCount))
     END AS stdDev
UNWIND rows AS row
WITH row,
     CASE WHEN maxScore = minScore THEN 1.0 ELSE (row.rawScore - minScore) / (maxScore - minScore) END AS minMaxScore,
     CASE WHEN stdDev = 0.0 THEN 0.5 ELSE 1.0 / (1.0 + exp(-((row.rawScore - meanScore) / stdDev))) END AS zScoreNormalized
WITH row,
     round((0.7 * minMaxScore + 0.3 * zScoreNormalized) * 10000.0) / 10000.0 AS score
RETURN row.movieId AS movieId,
       row.title AS title,
       score,
       {
         matchedGenres: row.matchedGenres,
         matchedActors: row.matchedActors,
         matchedDirectors: row.matchedDirectors,
         componentScores: {
           genreJaccard: round(row.genreJaccard * 10000.0) / 10000.0,
           actorJaccard: round(row.actorJaccard * 10000.0) / 10000.0,
           directorJaccard: round(row.directorJaccard * 10000.0) / 10000.0
         }
       } AS explanation
ORDER BY score DESC
LIMIT $limit
"""

GET_USER_CONTENT_RECOMMENDATIONS = """
/*
Algorithm: User profile content recommendations with weighted Jaccard components.

Parameters:
- $userId (int): target user
- $limit (int): max recommendations

Scores:
- genreScore in [0,1] from genre Jaccard
- actorScore in [0,1] from actor Jaccard
- directorScore in [0,1] from director Jaccard
- totalScore = 0.6*genreScore + 0.3*actorScore + 0.1*directorScore

Performance notes:
- User profile built from positively rated movies (>= 4.0)
- Candidate pool excludes movies already rated by user
*/
MATCH (u:User {userId: $userId})-[r:RATED]->(liked:Movie)
WHERE toFloat(r.rating) >= 4.0
WITH u, COLLECT(DISTINCT liked) AS likedMovies
UNWIND likedMovies AS liked
OPTIONAL MATCH (liked)-[:IN_GENRE]->(g:Genre)
WITH u, likedMovies, COLLECT(DISTINCT g.name) AS profileGenres
UNWIND likedMovies AS likedForActors
OPTIONAL MATCH (likedForActors)-[laRel]-(la)
WHERE type(laRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH u, likedMovies, profileGenres,
  COLLECT(DISTINCT CASE WHEN la.name IS NOT NULL THEN la.name ELSE toString(elementId(la)) END) AS profileActors
UNWIND likedMovies AS likedForDirectors
OPTIONAL MATCH (likedForDirectors)-[ldRel]-(ld)
WHERE type(ldRel) IN ['DIRECTED', 'DIRECTED_BY', 'HAS_DIRECTOR']
WITH u, profileGenres, profileActors,
  COLLECT(DISTINCT CASE WHEN ld.name IS NOT NULL THEN ld.name ELSE toString(elementId(ld)) END) AS profileDirectors

MATCH (rec:Movie)
WHERE NOT EXISTS((u)-[:RATED]->(rec))
OPTIONAL MATCH (rec)-[:IN_GENRE]->(rg:Genre)
WITH rec, profileGenres, profileActors, profileDirectors,
     COLLECT(DISTINCT rg.name) AS recGenres
OPTIONAL MATCH (rec)-[raRel]-(ra)
WHERE type(raRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH rec, profileGenres, profileActors, profileDirectors, recGenres,
  COLLECT(DISTINCT CASE WHEN ra.name IS NOT NULL THEN ra.name ELSE toString(elementId(ra)) END) AS recActors
OPTIONAL MATCH (rec)-[rdRel]-(rd)
WHERE type(rdRel) IN ['DIRECTED', 'DIRECTED_BY', 'HAS_DIRECTOR']
WITH rec, profileGenres, profileActors, profileDirectors, recGenres, recActors,
  COLLECT(DISTINCT CASE WHEN rd.name IS NOT NULL THEN rd.name ELSE toString(elementId(rd)) END) AS recDirectors

WITH rec,
     [genreName IN profileGenres WHERE genreName IN recGenres] AS matchedGenres,
     [actorName IN profileActors WHERE actorName IN recActors] AS matchedActors,
     [directorName IN profileDirectors WHERE directorName IN recDirectors] AS matchedDirectors,
     (SIZE(profileGenres) + SIZE(recGenres) - SIZE([genreName IN profileGenres WHERE genreName IN recGenres])) AS genreUnion,
     (SIZE(profileActors) + SIZE(recActors) - SIZE([actorName IN profileActors WHERE actorName IN recActors])) AS actorUnion,
     (SIZE(profileDirectors) + SIZE(recDirectors) - SIZE([directorName IN profileDirectors WHERE directorName IN recDirectors])) AS directorUnion
WITH rec,
     CASE WHEN genreUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedGenres)) / toFloat(genreUnion) END AS genreScore,
     CASE WHEN actorUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedActors)) / toFloat(actorUnion) END AS actorScore,
     CASE WHEN directorUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedDirectors)) / toFloat(directorUnion) END AS directorScore
WITH rec,
     (0.6 * genreScore + 0.3 * actorScore + 0.1 * directorScore) AS totalScore
WHERE totalScore > 0.0
RETURN rec.movieId AS movieId,
       rec.title AS title,
       round(totalScore * 10000.0) / 10000.0 AS totalScore
ORDER BY totalScore DESC
LIMIT $limit
"""
