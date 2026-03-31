"""Users endpoints"""
from fastapi import APIRouter, HTTPException, Query
from app.services.neo4j_service import neo4j_service
from app.services.recommendation_service import RecommendationService

router = APIRouter()
rec_service = RecommendationService(neo4j_service)

@router.get("/users")
async def get_users(limit: int = Query(100, ge=1, le=500)):
    """Get available users for selection"""
    users = await rec_service.get_users(limit)
    return {
        "users": users
    }

@router.get("/users/{user_id}/stats")
async def get_user_stats(user_id: int):
    """Get user statistics"""
    result = await rec_service.get_user_stats(user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "userId": user_id,
        "stats": result
    }