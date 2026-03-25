"""Recommendations endpoints"""
from fastapi import APIRouter, Query
from app.services.neo4j_service import neo4j_service
from app.services.recommendation_service import RecommendationService

router = APIRouter()
rec_service = RecommendationService(neo4j_service)

@router.get("/recommendations/{user_id}")
async def get_recommendations(
    user_id: int,
    limit: int = Query(10, ge=1, le=50)
):
    """Get collaborative filtering recommendations for a user"""
    results = await rec_service.get_collaborative_recommendations(user_id, limit)
    return {
        "userId": user_id,
        "type": "collaborative",
        "recommendations": results
    }

@router.get("/recommendations/{user_id}/content")
async def get_content_recommendations(
    user_id: int,
    limit: int = Query(10, ge=1, le=50)
):
    """Get content-based recommendations for a user"""
    results = await rec_service.get_content_recommendations(user_id, limit)
    return {
        "userId": user_id,
        "type": "content_based",
        "recommendations": results
    }