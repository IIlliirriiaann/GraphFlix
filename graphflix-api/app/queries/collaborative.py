"""Collaborative filtering queries"""

GET_COLLABORATIVE_RECOMMENDATIONS = """
/*
Algorithm: Advanced collaborative filtering with Jaccard similarity + rating-aware prediction.

Parameters:
- $userId (int): target user identifier
- $limit (int): max returned recommendations

Scoring:
1) Build neighbor users with aligned tastes (co-rated movies where |rating_u - rating_v| <= 1.0)
2) User similarity = Jaccard(commonRatedMovies, unionRatedMovies)
3) Keep neighbors with similarity > 0.1
4) predictedRating = SUM(similarity * neighborRating) / SUM(similarity)
5) score in [0,1] with min-max normalization blended with z-score logistic normalization

Performance notes:
- Traversal restricted to users who share at least one co-rated movie with target
- Aggregations are grouped by candidate movie
- Designed for top-N retrieval (default limit <= 50)

Example output row:
{
  movieId: 296,
  title: "Pulp Fiction (1994)",
  score: 0.8732,
  numSimilarUsers: 18,
  predictedRating: 4.36
}
*/
MATCH (target:User {userId: $userId})-[tr:RATED]->(tm:Movie)
WITH target,
     COLLECT(DISTINCT tm) AS targetMovies,
     COUNT(DISTINCT tm) AS targetMovieCount

MATCH (other:User)-[or:RATED]->(om:Movie)
WHERE other <> target
WITH target, targetMovies, targetMovieCount,
     other,
     COLLECT(DISTINCT om) AS otherMovies,
     COUNT(DISTINCT om) AS otherMovieCount
UNWIND targetMovies AS tMovie
WITH target, other, targetMovieCount, otherMovieCount, tMovie, otherMovies
WHERE tMovie IN otherMovies
WITH target, other, targetMovieCount, otherMovieCount,
     COLLECT(DISTINCT tMovie) AS commonMovies
WITH target,
     other,
     SIZE(commonMovies) AS commonCount,
     (targetMovieCount + otherMovieCount - SIZE(commonMovies)) AS unionCount
WHERE commonCount > 0 AND unionCount > 0
WITH target,
     other,
     toFloat(commonCount) / toFloat(unionCount) AS jaccardSimilarity
WHERE jaccardSimilarity > 0.1

MATCH (target)-[rTarget:RATED]->(cm:Movie)<-[rOther:RATED]-(other)
WHERE abs(toFloat(rTarget.rating) - toFloat(rOther.rating)) <= 1.0
WITH target, other, jaccardSimilarity, COUNT(DISTINCT cm) AS alignedCommonMovies
WHERE alignedCommonMovies > 0

MATCH (other)-[rRec:RATED]->(rec:Movie)
WHERE NOT EXISTS((target)-[:RATED]->(rec))
WITH rec,
     other,
     jaccardSimilarity,
     toFloat(rRec.rating) AS neighborRating
WITH rec,
     COUNT(DISTINCT other) AS numSimilarUsers,
     SUM(jaccardSimilarity * neighborRating) AS weightedRatingSum,
     SUM(jaccardSimilarity) AS similaritySum
WHERE similaritySum > 0
WITH rec,
     numSimilarUsers,
     (weightedRatingSum / similaritySum) AS predictedRating,
     (weightedRatingSum / similaritySum - 0.5) / 4.5 AS rawScore

WITH COLLECT({
    movieId: rec.movieId,
    title: rec.title,
    numSimilarUsers: numSimilarUsers,
    predictedRating: predictedRating,
    rawScore: rawScore
}) AS rows
WITH rows,
     SIZE(rows) AS rowCount,
     REDUCE(minScore = 1.0, row IN rows |
        CASE WHEN row.rawScore < minScore THEN row.rawScore ELSE minScore END
     ) AS minScore,
     REDUCE(maxScore = 0.0, row IN rows |
        CASE WHEN row.rawScore > maxScore THEN row.rawScore ELSE maxScore END
     ) AS maxScore,
     REDUCE(total = 0.0, row IN rows | total + row.rawScore) AS totalScore
WITH rows, rowCount, minScore, maxScore,
     CASE WHEN rowCount = 0 THEN 0.0 ELSE totalScore / toFloat(rowCount) END AS meanScore
WITH rows, rowCount, minScore, maxScore, meanScore,
     CASE
       WHEN rowCount = 0 THEN 0.0
       ELSE sqrt(REDUCE(varAcc = 0.0, row IN rows | varAcc + (row.rawScore - meanScore) * (row.rawScore - meanScore)) / toFloat(rowCount))
     END AS stdDev
UNWIND rows AS row
WITH row, minScore, maxScore, meanScore, stdDev,
     CASE
       WHEN maxScore = minScore THEN 1.0
       ELSE (row.rawScore - minScore) / (maxScore - minScore)
     END AS minMaxScore,
     CASE
       WHEN stdDev = 0.0 THEN 0.5
       ELSE 1.0 / (1.0 + exp(-((row.rawScore - meanScore) / stdDev)))
     END AS zScoreNormalized
WITH row,
     round((0.7 * minMaxScore + 0.3 * zScoreNormalized) * 10000.0) / 10000.0 AS score
RETURN row.movieId AS movieId,
       row.title AS title,
       score,
       row.numSimilarUsers AS numSimilarUsers,
       round(row.predictedRating * 100.0) / 100.0 AS predictedRating
ORDER BY score DESC, predictedRating DESC, numSimilarUsers DESC
LIMIT $limit
"""


GET_HYBRID_RECOMMENDATIONS = """
/*
Algorithm: Hybrid recommendation blending collaborative and content-based signals.

Parameters:
- $userId (int): target user identifier
- $limit (int): max recommendations (typically 10)
- $collaborativeWeight (float, optional): default 0.6
- $contentWeight (float, optional): default 0.4

Scoring:
1) Build collaborative candidate scores (rating-aware Jaccard neighbors)
2) Build content score from user's liked-movie profile (genres/actors/directors)
3) hybridScore = collabWeight*collaborativeScore + contentWeight*contentScore
4) Apply slight boosts: popularity (+5%), recency (+5%)
5) Diversity post-filter: keep max 3 movies per primary genre before final LIMIT

Performance notes:
- Candidate set constrained by collaborative neighbors and unseen movies
- Content/profile features are pre-aggregated once per request
- Diversity filter is list-based after scoring and ordering

Example output row:
{
  movieId: 858,
  title: "Godfather, The (1972)",
  hybridScore: 0.8112,
  collaborativeScore: 0.79,
  contentScore: 0.76,
  genres: ["Crime", "Drama"]
}
*/
MATCH (target:User {userId: $userId})
WITH target,
     coalesce(toFloat($collaborativeWeight), 0.6) AS collaborativeWeight,
     coalesce(toFloat($contentWeight), 0.4) AS contentWeight

MATCH (target)-[tr:RATED]->(tm:Movie)
WITH target, collaborativeWeight, contentWeight,
     COLLECT(DISTINCT tm) AS targetMovies,
     COUNT(DISTINCT tm) AS targetMovieCount

MATCH (other:User)-[or:RATED]->(om:Movie)
WHERE other <> target
WITH target, collaborativeWeight, contentWeight,
     targetMovies, targetMovieCount,
     other,
     COLLECT(DISTINCT om) AS otherMovies,
     COUNT(DISTINCT om) AS otherMovieCount
UNWIND targetMovies AS tMovie
WITH target, collaborativeWeight, contentWeight,
     other, targetMovieCount, otherMovieCount, tMovie, otherMovies
WHERE tMovie IN otherMovies
WITH target, collaborativeWeight, contentWeight,
     other, targetMovieCount, otherMovieCount,
     COLLECT(DISTINCT tMovie) AS commonMovies
WITH target, collaborativeWeight, contentWeight,
     other,
     SIZE(commonMovies) AS commonCount,
     (targetMovieCount + otherMovieCount - SIZE(commonMovies)) AS unionCount
WHERE commonCount > 0 AND unionCount > 0
WITH target, collaborativeWeight, contentWeight,
     other,
     toFloat(commonCount) / toFloat(unionCount) AS jaccardSimilarity
WHERE jaccardSimilarity > 0.1

MATCH (target)-[rTarget:RATED]->(cm:Movie)<-[rOther:RATED]-(other)
WHERE abs(toFloat(rTarget.rating) - toFloat(rOther.rating)) <= 1.0
WITH target, collaborativeWeight, contentWeight,
     other, jaccardSimilarity, COUNT(DISTINCT cm) AS alignedCommonMovies
WHERE alignedCommonMovies > 0

MATCH (other)-[rRec:RATED]->(rec:Movie)
WHERE NOT EXISTS((target)-[:RATED]->(rec))
WITH target, collaborativeWeight, contentWeight,
     rec,
     SUM(jaccardSimilarity * toFloat(rRec.rating)) AS weightedRatingSum,
     SUM(jaccardSimilarity) AS similaritySum,
     COUNT(DISTINCT other) AS numSimilarUsers
WHERE similaritySum > 0
WITH target, collaborativeWeight, contentWeight,
     rec,
     numSimilarUsers,
     (weightedRatingSum / similaritySum) AS predictedRating
WITH target, collaborativeWeight, contentWeight,
     COLLECT({
        rec: rec,
        movieId: rec.movieId,
        title: rec.title,
        numSimilarUsers: numSimilarUsers,
        collaborativeRaw: (predictedRating - 0.5) / 4.5
     }) AS candidates

MATCH (target)-[liked:RATED]->(likedMovie:Movie)
WHERE toFloat(liked.rating) >= 4.0
OPTIONAL MATCH (likedMovie)-[:IN_GENRE]->(likedGenre:Genre)
WITH target, collaborativeWeight, contentWeight, candidates,
     COLLECT(DISTINCT likedGenre.name) AS userGenres
OPTIONAL MATCH (likedMovie)-[likedActorRel]-(likedActor)
WHERE type(likedActorRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH target, collaborativeWeight, contentWeight, candidates, userGenres,
  COLLECT(DISTINCT CASE WHEN likedActor.name IS NOT NULL THEN likedActor.name ELSE toString(elementId(likedActor)) END) AS userActors
OPTIONAL MATCH (likedMovie)-[likedDirectorRel]-(likedDirector)
WHERE type(likedDirectorRel) IN ['DIRECTED', 'DIRECTED_BY', 'HAS_DIRECTOR']
WITH collaborativeWeight, contentWeight, candidates,
     userGenres,
     userActors,
  COLLECT(DISTINCT CASE WHEN likedDirector.name IS NOT NULL THEN likedDirector.name ELSE toString(elementId(likedDirector)) END) AS userDirectors

UNWIND candidates AS candidate
WITH collaborativeWeight, contentWeight,
     candidate,
     userGenres, userActors, userDirectors,
     candidate.rec AS rec
OPTIONAL MATCH (rec)-[:IN_GENRE]->(recGenre:Genre)
WITH collaborativeWeight, contentWeight, candidate, rec,
     userGenres, userActors, userDirectors,
     COLLECT(DISTINCT recGenre.name) AS recGenres
OPTIONAL MATCH (rec)-[recActorRel]-(recActor)
WHERE type(recActorRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH collaborativeWeight, contentWeight, candidate, rec,
     userGenres, userActors, userDirectors, recGenres,
  COLLECT(DISTINCT CASE WHEN recActor.name IS NOT NULL THEN recActor.name ELSE toString(elementId(recActor)) END) AS recActors
OPTIONAL MATCH (rec)-[recDirectorRel]-(recDirector)
WHERE type(recDirectorRel) IN ['DIRECTED', 'DIRECTED_BY', 'HAS_DIRECTOR']
WITH collaborativeWeight, contentWeight, candidate, rec,
     userGenres, userActors, userDirectors,
     recGenres, recActors,
  COLLECT(DISTINCT CASE WHEN recDirector.name IS NOT NULL THEN recDirector.name ELSE toString(elementId(recDirector)) END) AS recDirectors

WITH collaborativeWeight, contentWeight, candidate, rec, recGenres,
     [g IN userGenres WHERE g IN recGenres] AS matchedGenres,
     [a IN userActors WHERE a IN recActors] AS matchedActors,
     [d IN userDirectors WHERE d IN recDirectors] AS matchedDirectors,
     (SIZE(userGenres) + SIZE(recGenres) - SIZE([g IN userGenres WHERE g IN recGenres])) AS genreUnion,
     (SIZE(userActors) + SIZE(recActors) - SIZE([a IN userActors WHERE a IN recActors])) AS actorUnion,
     (SIZE(userDirectors) + SIZE(recDirectors) - SIZE([d IN userDirectors WHERE d IN recDirectors])) AS directorUnion
WITH collaborativeWeight, contentWeight, candidate, rec, recGenres,
     CASE WHEN genreUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedGenres)) / toFloat(genreUnion) END AS genreJaccard,
     CASE WHEN actorUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedActors)) / toFloat(actorUnion) END AS actorJaccard,
     CASE WHEN directorUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedDirectors)) / toFloat(directorUnion) END AS directorJaccard

OPTIONAL MATCH (rec)<-[allRatings:RATED]-()
WITH collaborativeWeight, contentWeight, candidate, rec, recGenres,
     (0.6 * genreJaccard + 0.3 * actorJaccard + 0.1 * directorJaccard) AS contentRaw,
     avg(toFloat(allRatings.rating)) AS avgRating,
     count(allRatings) AS numRatings
WITH collaborativeWeight, contentWeight,
     candidate,
     rec,
     recGenres,
     contentRaw,
     candidate.collaborativeRaw AS collaborativeRaw,
     coalesce(avgRating, 0.0) AS avgRating,
     toFloat(coalesce(numRatings, 0)) AS numRatings,
     coalesce(toFloat(rec.year), toFloat(rec.releaseYear), 0.0) AS releaseYear

WITH COLLECT({
    movieId: candidate.movieId,
    title: candidate.title,
    genres: recGenres,
    collaborativeRaw: collaborativeRaw,
    contentRaw: contentRaw,
    popularityRaw: (coalesce(avgRating, 0.0) / 5.0) * (1.0 - exp(-numRatings / 50.0)),
    releaseYear: releaseYear
}) AS rows,
collaborativeWeight,
contentWeight

WITH rows, collaborativeWeight, contentWeight,
     REDUCE(minC = 1.0, row IN rows | CASE WHEN row.collaborativeRaw < minC THEN row.collaborativeRaw ELSE minC END) AS minCollab,
     REDUCE(maxC = 0.0, row IN rows | CASE WHEN row.collaborativeRaw > maxC THEN row.collaborativeRaw ELSE maxC END) AS maxCollab,
     REDUCE(minCt = 1.0, row IN rows | CASE WHEN row.contentRaw < minCt THEN row.contentRaw ELSE minCt END) AS minContent,
     REDUCE(maxCt = 0.0, row IN rows | CASE WHEN row.contentRaw > maxCt THEN row.contentRaw ELSE maxCt END) AS maxContent,
     REDUCE(minP = 1.0, row IN rows | CASE WHEN row.popularityRaw < minP THEN row.popularityRaw ELSE minP END) AS minPopularity,
     REDUCE(maxP = 0.0, row IN rows | CASE WHEN row.popularityRaw > maxP THEN row.popularityRaw ELSE maxP END) AS maxPopularity,
     REDUCE(minY = 9999.0, row IN rows | CASE WHEN row.releaseYear < minY THEN row.releaseYear ELSE minY END) AS minYear,
     REDUCE(maxY = 0.0, row IN rows | CASE WHEN row.releaseYear > maxY THEN row.releaseYear ELSE maxY END) AS maxYear

UNWIND rows AS row
WITH row,
     CASE WHEN maxCollab = minCollab THEN row.collaborativeRaw ELSE (row.collaborativeRaw - minCollab) / (maxCollab - minCollab) END AS collaborativeScore,
     CASE WHEN maxContent = minContent THEN row.contentRaw ELSE (row.contentRaw - minContent) / (maxContent - minContent) END AS contentScore,
     CASE WHEN maxPopularity = minPopularity THEN row.popularityRaw ELSE (row.popularityRaw - minPopularity) / (maxPopularity - minPopularity) END AS popularityScore,
     CASE WHEN maxYear = minYear THEN 0.0 ELSE (row.releaseYear - minYear) / (maxYear - minYear) END AS recencyScore,
     collaborativeWeight,
     contentWeight
WITH row,
     collaborativeScore,
     contentScore,
     round((
       collaborativeWeight * collaborativeScore +
       contentWeight * contentScore +
       0.05 * popularityScore +
       0.05 * recencyScore
     ) * 10000.0) / 10000.0 AS hybridScore
ORDER BY hybridScore DESC

WITH COLLECT({
    movieId: row.movieId,
    title: row.title,
    genres: row.genres,
    hybridScore: CASE WHEN hybridScore > 1.0 THEN 1.0 ELSE hybridScore END,
    collaborativeScore: round(collaborativeScore * 10000.0) / 10000.0,
    contentScore: round(contentScore * 10000.0) / 10000.0
}) AS ranked
UNWIND ranked AS rec
WITH rec,
     CASE WHEN size(rec.genres) = 0 THEN 'Unknown' ELSE rec.genres[0] END AS primaryGenre
ORDER BY rec.hybridScore DESC
WITH primaryGenre, COLLECT(rec) AS genreRows
WITH genreRows[..3] AS cappedRows
UNWIND cappedRows AS diverseRec
WITH diverseRec
ORDER BY diverseRec.hybridScore DESC
RETURN diverseRec.movieId AS movieId,
       diverseRec.title AS title,
       diverseRec.hybridScore AS hybridScore,
       diverseRec.collaborativeScore AS collaborativeScore,
       diverseRec.contentScore AS contentScore,
       diverseRec.genres AS genres
LIMIT $limit
"""


GET_CONFIGURABLE_WEIGHT_RECOMMENDATIONS = """
/*
Algorithm: Configurable composite recommendation scoring.

Parameters:
- $userId (int)
- $limit (int)
- $genreWeight (float)
- $actorWeight (float)
- $ratingWeight (float)
- $popularityWeight (float)

Constraint:
- Caller must provide weights that sum to 1.0

Component scores (all normalized to [0,1]):
- genreScore: Jaccard between user favorite genres and movie genres
- actorScore: Jaccard between user favorite actors and movie actors
- ratingScore: collaborative predicted rating normalized from [0.5,5.0]
- popularityScore: quality-weighted popularity from average rating and rating volume

compositeScore =
  genreWeight * genreScore +
  actorWeight * actorScore +
  ratingWeight * ratingScore +
  popularityWeight * popularityScore

Performance notes:
- Uses collaborative candidate generation first to reduce search space
- Reuses user profile sets for content matching

Example output row:
{
  movieId: 2571,
  title: "Matrix, The (1999)",
  compositeScore: 0.8021,
  breakdown: {
    genreScore: 0.71,
    actorScore: 0.33,
    ratingScore: 0.92,
    popularityScore: 0.80,
    weights: {genreWeight: 0.25, actorWeight: 0.15, ratingWeight: 0.45, popularityWeight: 0.15}
  }
}
*/
MATCH (target:User {userId: $userId})
WITH target,
     toFloat($genreWeight) AS genreWeight,
     toFloat($actorWeight) AS actorWeight,
     toFloat($ratingWeight) AS ratingWeight,
     toFloat($popularityWeight) AS popularityWeight

MATCH (target)-[tr:RATED]->(tm:Movie)
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     COLLECT(DISTINCT tm) AS targetMovies,
     COUNT(DISTINCT tm) AS targetMovieCount

MATCH (other:User)-[:RATED]->(om:Movie)
WHERE other <> target
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     targetMovies, targetMovieCount,
     other,
     COLLECT(DISTINCT om) AS otherMovies,
     COUNT(DISTINCT om) AS otherMovieCount
UNWIND targetMovies AS tMovie
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     other, targetMovieCount, otherMovieCount, tMovie, otherMovies
WHERE tMovie IN otherMovies
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     other, targetMovieCount, otherMovieCount,
     COLLECT(DISTINCT tMovie) AS commonMovies
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     other,
     SIZE(commonMovies) AS commonCount,
     (targetMovieCount + otherMovieCount - SIZE(commonMovies)) AS unionCount
WHERE commonCount > 0 AND unionCount > 0
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     other,
     toFloat(commonCount) / toFloat(unionCount) AS jaccardSimilarity
WHERE jaccardSimilarity > 0.1
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     other,
     jaccardSimilarity
ORDER BY jaccardSimilarity DESC
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     COLLECT({other: other, similarity: jaccardSimilarity})[..150] AS topNeighbors
UNWIND topNeighbors AS topNeighbor
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     topNeighbor.other AS other,
     topNeighbor.similarity AS jaccardSimilarity

MATCH (target)-[rTarget:RATED]->(cm:Movie)<-[rOther:RATED]-(other)
WHERE abs(toFloat(rTarget.rating) - toFloat(rOther.rating)) <= 1.0
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     other, jaccardSimilarity, COUNT(DISTINCT cm) AS alignedCommonMovies
WHERE alignedCommonMovies > 0

MATCH (other)-[rRec:RATED]->(rec:Movie)
WHERE NOT EXISTS((target)-[:RATED]->(rec))
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     rec,
     SUM(jaccardSimilarity * toFloat(rRec.rating)) AS weightedRatingSum,
     SUM(jaccardSimilarity) AS similaritySum
WHERE similaritySum > 0
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
     rec,
     (weightedRatingSum / similaritySum) AS predictedRating
ORDER BY predictedRating DESC
WITH target, genreWeight, actorWeight, ratingWeight, popularityWeight,
    COLLECT({
     rec: rec,
     movieId: rec.movieId,
     title: rec.title,
     predictedRating: predictedRating
  })[..(toInteger($limit) * 4)] AS candidates

MATCH (target)-[liked:RATED]->(likedMovie:Movie)
WHERE toFloat(liked.rating) >= 4.0
OPTIONAL MATCH (likedMovie)-[:IN_GENRE]->(likedGenre:Genre)
WITH candidates, genreWeight, actorWeight, ratingWeight, popularityWeight,
    COLLECT(DISTINCT likedGenre.name) AS userGenres
OPTIONAL MATCH (likedMovie)-[likedActorRel]-(likedActor)
WHERE type(likedActorRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH candidates, genreWeight, actorWeight, ratingWeight, popularityWeight,
    userGenres,
    COLLECT(DISTINCT CASE WHEN likedActor.name IS NOT NULL THEN likedActor.name ELSE toString(elementId(likedActor)) END) AS userActors

UNWIND candidates AS candidate
WITH candidate, genreWeight, actorWeight, ratingWeight, popularityWeight,
    userGenres, userActors, candidate.rec AS rec
OPTIONAL MATCH (rec)-[:IN_GENRE]->(recGenre:Genre)
WITH candidate, rec, genreWeight, actorWeight, ratingWeight, popularityWeight,
    userGenres, userActors,
    COLLECT(DISTINCT recGenre.name) AS recGenres
OPTIONAL MATCH (rec)-[recActorRel]-(recActor)
WHERE type(recActorRel) IN ['ACTED_IN', 'HAS_ACTOR', 'FEATURES_ACTOR']
WITH candidate, rec, genreWeight, actorWeight, ratingWeight, popularityWeight,
    userGenres, userActors, recGenres,
    COLLECT(DISTINCT CASE WHEN recActor.name IS NOT NULL THEN recActor.name ELSE toString(elementId(recActor)) END) AS recActors

WITH candidate, rec, genreWeight, actorWeight, ratingWeight, popularityWeight,
    [g IN userGenres WHERE g IN recGenres] AS matchedGenres,
    [a IN userActors WHERE a IN recActors] AS matchedActors,
    (SIZE(userGenres) + SIZE(recGenres) - SIZE([g IN userGenres WHERE g IN recGenres])) AS genreUnion,
    (SIZE(userActors) + SIZE(recActors) - SIZE([a IN userActors WHERE a IN recActors])) AS actorUnion
WITH candidate, rec, genreWeight, actorWeight, ratingWeight, popularityWeight,
    CASE WHEN genreUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedGenres)) / toFloat(genreUnion) END AS genreScore,
    CASE WHEN actorUnion = 0 THEN 0.0 ELSE toFloat(SIZE(matchedActors)) / toFloat(actorUnion) END AS actorScore

OPTIONAL MATCH (rec)<-[allRatings:RATED]-()
WITH candidate, rec, genreScore, actorScore,
    genreWeight, actorWeight, ratingWeight, popularityWeight,
    avg(toFloat(allRatings.rating)) AS avgRating,
    count(allRatings) AS numRatings
WITH candidate,
    genreScore,
    actorScore,
    (candidate.predictedRating - 0.5) / 4.5 AS ratingScore,
    (coalesce(avgRating, 0.0) / 5.0) * (1.0 - exp(-toFloat(coalesce(numRatings, 0)) / 50.0)) AS popularityRaw,
    genreWeight,
    actorWeight,
    ratingWeight,
    popularityWeight

WITH COLLECT({
  movieId: candidate.movieId,
  title: candidate.title,
   genreScore: genreScore,
   actorScore: actorScore,
   ratingScore: ratingScore,
   popularityRaw: popularityRaw
}) AS rows,
genreWeight, actorWeight, ratingWeight, popularityWeight

WITH rows, genreWeight, actorWeight, ratingWeight, popularityWeight,
     REDUCE(minP = 1.0, row IN rows | CASE WHEN row.popularityRaw < minP THEN row.popularityRaw ELSE minP END) AS minPopularity,
     REDUCE(maxP = 0.0, row IN rows | CASE WHEN row.popularityRaw > maxP THEN row.popularityRaw ELSE maxP END) AS maxPopularity
UNWIND rows AS row
WITH row,
     CASE WHEN maxPopularity = minPopularity THEN row.popularityRaw ELSE (row.popularityRaw - minPopularity) / (maxPopularity - minPopularity) END AS popularityScore,
     genreWeight,
     actorWeight,
     ratingWeight,
     popularityWeight
WITH row,
     popularityScore,
     genreWeight,
     actorWeight,
     ratingWeight,
     popularityWeight,
     round((
       genreWeight * row.genreScore +
       actorWeight * row.actorScore +
       ratingWeight * row.ratingScore +
       popularityWeight * popularityScore
     ) * 10000.0) / 10000.0 AS compositeScore
RETURN row.movieId AS movieId,
       row.title AS title,
       compositeScore,
       {
         genreScore: round(row.genreScore * 10000.0) / 10000.0,
         actorScore: round(row.actorScore * 10000.0) / 10000.0,
         ratingScore: round(row.ratingScore * 10000.0) / 10000.0,
         popularityScore: round(popularityScore * 10000.0) / 10000.0,
         weights: {
           genreWeight: genreWeight,
           actorWeight: actorWeight,
           ratingWeight: ratingWeight,
           popularityWeight: popularityWeight
         }
       } AS breakdown
ORDER BY compositeScore DESC
LIMIT $limit
"""
