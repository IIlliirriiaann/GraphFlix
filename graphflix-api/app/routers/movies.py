"""Movies endpoints"""
from fastapi import APIRouter, HTTPException, Query
from app.services.neo4j_service import neo4j_service
from app.services.recommendation_service import RecommendationService

router = APIRouter()
rec_service = RecommendationService(neo4j_service)

@router.get("/movies/{movie_id}")
async def get_movie(movie_id: int):
    """Get movie details"""
    result = await rec_service.get_movie_details(movie_id)
    if not result:
        raise HTTPException(status_code=404, detail="Movie not found")
    return result

@router.get("/movies/{movie_id}/similar")
async def get_similar_movies(
    movie_id: int,
    limit: int = Query(10, ge=1, le=50)
):
    """Get similar movies based on genres"""
    results = await rec_service.get_similar_movies(movie_id, limit)
    return {
        "movieId": movie_id,
        "similar": results
    }

@router.get("/movies/top")
async def get_top_movies(
    genre: str = Query(..., description="Genre name (e.g., 'Sci-Fi', 'Action')"),
    limit: int = Query(10, ge=1, le=50),
    min_ratings: int = Query(50, ge=1)
):
    """Get top-rated movies by genre"""
    results = await rec_service.get_top_movies(genre, limit, min_ratings)
    return {
        "genre": genre,
        "movies": results
    }