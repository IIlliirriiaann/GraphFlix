"""Recommendations endpoints"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.neo4j_service import neo4j_service
from app.services.recommendation_service import RecommendationService

router = APIRouter()
rec_service = RecommendationService(neo4j_service)


class RecommendationWeights(BaseModel):
    genre: float = Field(..., ge=0)
    rating: float = Field(..., ge=0)


class CustomRecommendationsRequest(BaseModel):
    userId: int
    weights: RecommendationWeights
    limit: int = Field(10, ge=1, le=50)

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


@router.post("/recommendations/custom")
async def get_custom_recommendations(payload: CustomRecommendationsRequest):
    """Get weighted recommendations with dynamic algorithm weights."""
    weight_values = payload.weights.model_dump() if hasattr(payload.weights, "model_dump") else payload.weights.dict()
    if sum(weight_values.values()) <= 0:
        raise HTTPException(status_code=400, detail="At least one weight must be greater than 0")

    results = await rec_service.get_custom_recommendations(
        user_id=payload.userId,
        weights=weight_values,
        limit=payload.limit,
    )
    return {
        "userId": payload.userId,
        "type": "custom_weighted",
        "weights": weight_values,
        "recommendations": results,
    }