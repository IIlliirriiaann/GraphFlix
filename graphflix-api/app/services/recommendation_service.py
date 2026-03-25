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
        """Collaborative filtering recommendations"""
        movies = await self.db.execute_read(
            collaborative.GET_COLLABORATIVE_RECOMMENDATIONS,
            {"userId": user_id, "limit": limit}
        )
        return await self._hydrate_movie_list(movies)
    
    async def get_content_recommendations(self, user_id: int, limit: int = 10):
        """Content-based recommendations"""
        movies = await self.db.execute_read(
            content_based.GET_USER_CONTENT_RECOMMENDATIONS,
            {"userId": user_id, "limit": limit}
        )
        return await self._hydrate_movie_list(movies)
    
    async def get_similar_movies(self, movie_id: int, limit: int = 10):
        """Similar movies"""
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