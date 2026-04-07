from app.services.neo4j_service import Neo4jService
from app.queries import collaborative, content_based, utils
from typing import Any

class RecommendationService:
    def __init__(self, neo4j_service: Neo4jService):
        self.db = neo4j_service

    async def _hydrate_movie_list(self, movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Enrich a ranked movie list with shared movie details in one batch query."""
        if not movies:
            return []

        movie_ids = []
        seen = set()
        for movie in movies:
            movie_id = movie.get("movieId")
            if movie_id is None or movie_id in seen:
                continue
            seen.add(movie_id)
            movie_ids.append(movie_id)

        details_rows = await self.db.execute_read(
            utils.GET_MOVIES_DETAILS_BY_IDS,
            {"movieIds": movie_ids}
        )
        details_by_id = {row["movieId"]: row for row in details_rows}

        # Keep original ordering/ranking metadata while enriching each movie.
        return [
            {
                **details_by_id.get(movie.get("movieId"), {}),
                **movie,
            }
            for movie in movies
        ]
    
    async def get_collaborative_recommendations(self, user_id: int, limit: int = 10):
        """Advanced collaborative filtering with Jaccard similarity and rating-aware prediction.
        
        Returns:
        - movieId: numeric movie identifier
        - title: movie title
        - score: normalized [0,1] blending min-max and z-score normalization
        - numSimilarUsers: count of users with similarity > 0.1 who rated this movie
        - predictedRating: weighted average rating from similar users
        """
        movies = await self.db.execute_read(
            collaborative.GET_COLLABORATIVE_RECOMMENDATIONS,
            {"userId": user_id, "limit": limit}
        )
        return await self._hydrate_movie_list(movies)
    
    async def get_content_recommendations(self, user_id: int, limit: int = 10):
        """Content-based recommendations from user's preferred movies profile.
        
        Builds user profile from movies rated >= 4.0, then recommends movies
        matching genres, actors, and directors with weighted Jaccard similarity.
        
        Returns:
        - movieId: numeric movie identifier
        - title: movie title
        - totalScore: composite score [0,1] from genre (0.6) + actor (0.3) + director (0.1)
        """
        movies = await self.db.execute_read(
            content_based.GET_USER_CONTENT_RECOMMENDATIONS,
            {"userId": user_id, "limit": limit}
        )
        return await self._hydrate_movie_list(movies)

    async def get_hybrid_recommendations(
        self,
        user_id: int,
        collaborative_weight: float = 0.6,
        content_weight: float = 0.4,
        limit: int = 10
    ):
        """Hybrid recommendations blending collaborative and content-based signals.
        
        Combines two scaled scores using configurable weights, with boosts for
        popularity (+5%) and recency (+5%). Applies diversity filter to ensure
        max 3 movies per genre in top-N results.
        
        Parameters:
        - collaborative_weight: weight for collaborative score [0, 1]
        - content_weight: weight for content score [0, 1]
        - limit: max recommendations returned (before diversity filtering)
        
        Returns:
        - movieId: numeric movie identifier
        - title: movie title
        - hybridScore: composite score [0,1]
        - collaborativeScore: normalized collaborative component
        - contentScore: normalized content component
        - genres: list of associated genres
        """
        movies = await self.db.execute_read(
            collaborative.GET_HYBRID_RECOMMENDATIONS,
            {
                "userId": user_id,
                "limit": limit,
                "collaborativeWeight": collaborative_weight,
                "contentWeight": content_weight
            }
        )
        return await self._hydrate_movie_list(movies)

    async def get_configurable_weight_recommendations(
        self,
        user_id: int,
        genre_weight: float = 0.25,
        actor_weight: float = 0.15,
        rating_weight: float = 0.45,
        popularity_weight: float = 0.15,
        limit: int = 10
    ):
        """Configurable composite scoring with detailed component breakdown.
        
        All weights must sum to 1.0. Combines four normalized components:
        - genreScore: Jaccard similarity of genres
        - actorScore: Jaccard similarity of actors
        - ratingScore: collaborative predicted rating [0.5, 5.0] normalized to [0,1]
        - popularityScore: quality-weighted popularity from avg rating and volume
        
        Parameters:
        - genre_weight, actor_weight, rating_weight, popularity_weight: all [0, 1]
        
        Returns:
        - movieId: numeric movie identifier
        - title: movie title
        - compositeScore: weighted combination [0,1]
        - breakdown: dict with genreScore, actorScore, ratingScore, popularityScore, and weights used
        """
        # Validate weights sum to 1.0 (with small tolerance for float comparison)
        weight_sum = genre_weight + actor_weight + rating_weight + popularity_weight
        if not (0.99 <= weight_sum <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {weight_sum}")
        
        movies = await self.db.execute_read(
            collaborative.GET_CONFIGURABLE_WEIGHT_RECOMMENDATIONS,
            {
                "userId": user_id,
                "limit": limit,
                "genreWeight": genre_weight,
                "actorWeight": actor_weight,
                "ratingWeight": rating_weight,
                "popularityWeight": popularity_weight
            }
        )
        return await self._hydrate_movie_list(movies)

    async def get_custom_recommendations(
        self,
        user_id: int,
        weights: dict[str, float],
        limit: int = 10
    ):
        """Legacy wrapper for backward compatibility with custom weighted recommendations.
        
        Maps legacy 'genre' and 'rating' keys to new 4-component model.
        """
        fetch_limit = max(limit * 3, limit)

        collaborative_movies = await self.db.execute_read(
            collaborative.GET_COLLABORATIVE_RECOMMENDATIONS,
            {"userId": user_id, "limit": fetch_limit}
        )
        content_movies = await self.db.execute_read(
            content_based.GET_USER_CONTENT_RECOMMENDATIONS,
            {"userId": user_id, "limit": fetch_limit}
        )

        weighted_movies: dict[int, dict[str, Any]] = {}

        def _accumulate(movies: list[dict[str, Any]], key: str, raw_score_key: str):
            weight = float(weights.get(key, 0.0))
            if weight <= 0:
                return

            max_raw_score = max((float(movie.get(raw_score_key, 0.0)) for movie in movies), default=0.0)
            if max_raw_score <= 0:
                return

            for movie in movies:
                movie_id = movie.get("movieId")
                if movie_id is None:
                    continue

                raw_score = float(movie.get(raw_score_key, 0.0))
                normalized_score = raw_score / max_raw_score
                contribution = normalized_score * weight

                existing = weighted_movies.setdefault(
                    movie_id,
                    {
                        "movieId": movie_id,
                        "title": movie.get("title"),
                        "weightedScore": 0.0,
                        "sourceScores": {},
                    },
                )
                existing["weightedScore"] += contribution
                existing["sourceScores"][key] = {
                    "raw": raw_score,
                    "normalized": normalized_score,
                    "weight": weight,
                    "contribution": contribution,
                }

        _accumulate(collaborative_movies, "rating", "score")
        _accumulate(content_movies, "genre", "totalScore")

        ranked = sorted(
            weighted_movies.values(),
            key=lambda movie: movie["weightedScore"],
            reverse=True,
        )[:limit]

        return await self._hydrate_movie_list(ranked)
    
    async def get_similar_movies(self, movie_id: int, limit: int = 10):
        """Similar movies based on weighted genre, actor, and director Jaccard similarity.
        
        Weights: genres (0.6), actors (0.3), directors (0.1).
        Returns normalized scores with explanation of matched content.
        
        Returns:
        - movieId: numeric movie identifier
        - title: movie title
        - score: normalized [0,1]
        - explanation: dict with matchedGenres, matchedActors, matchedDirectors, componentScores
        """
        movies = await self.db.execute_read(
            content_based.GET_SIMILAR_MOVIES_BY_GENRE,
            {"movieId": movie_id, "limit": limit}
        )
        return await self._hydrate_movie_list(movies)
    
    async def get_movie_details(self, movie_id: int):
        """Movie details"""
        results = await self.db.execute_read(
            utils.GET_MOVIE_DETAILS,
            {"movieId": movie_id}
        )
        return results[0] if results else None
    
    async def get_top_movies(self, genre: str, limit: int = 10, min_ratings: int = 50):
        """Top movies by genre"""
        movies = await self.db.execute_read(
            utils.GET_TOP_MOVIES_BY_GENRE,
            {"genre": genre, "limit": limit, "minRatings": min_ratings}
        )
        return await self._hydrate_movie_list(movies)
    
    async def get_user_stats(self, user_id: int):  # int
        """User statistics"""
        results = await self.db.execute_read(
            utils.GET_USER_STATS,
            {"userId": user_id}
        )
        return results[0] if results else None

    async def get_users(self, limit: int = 100):
        """List users for selection in the UI"""
        return await self.db.execute_read(
            utils.GET_USERS,
            {"limit": limit}
        )
