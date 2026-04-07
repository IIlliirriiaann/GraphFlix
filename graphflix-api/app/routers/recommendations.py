"""Recommendations endpoints"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator
from app.services.neo4j_service import neo4j_service
from app.services.recommendation_service import RecommendationService

router = APIRouter()
rec_service = RecommendationService(neo4j_service)


class RecommendationWeights(BaseModel):
    """Legacy weights format for backward compatibility."""
    genre: float = Field(..., ge=0)
    rating: float = Field(..., ge=0)


class HybridWeights(BaseModel):
    """Weights for hybrid recommendation combining collaborative and content signals."""
    collaborativeWeight: float = Field(0.6, ge=0, le=1)
    contentWeight: float = Field(0.4, ge=0, le=1)
    
    @validator('collaborativeWeight', 'contentWeight')
    def weights_sum(cls, v, values):
        if 'collaborativeWeight' in values and 'contentWeight' in values:
            collab = values.get('collaborativeWeight', 0.6)
            content = values.get('contentWeight', 0.4)
            total = collab + content
            if not (0.99 <= total <= 1.01):
                raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v


class ConfigurableWeights(BaseModel):
    """Weights for fully configurable composite scoring (must sum to 1.0)."""
    genreWeight: float = Field(0.25, ge=0, le=1)
    actorWeight: float = Field(0.15, ge=0, le=1)
    ratingWeight: float = Field(0.45, ge=0, le=1)
    popularityWeight: float = Field(0.15, ge=0, le=1)
    
    @validator('genreWeight', 'actorWeight', 'ratingWeight', 'popularityWeight')
    def weights_sum_to_one(cls, v, values):
        all_weights = [
            values.get('genreWeight', 0.25),
            values.get('actorWeight', 0.15),
            values.get('ratingWeight', 0.45),
            values.get('popularityWeight', 0.15)
        ]
        # Only validate if all weights are present
        if len([w for w in all_weights if w is not None]) == 4:
            total = sum(all_weights)
            if not (0.99 <= total <= 1.01):
                raise ValueError(f"All weights must sum to 1.0, got {total}")
        return v


class CustomRecommendationsRequest(BaseModel):
    userId: int
    weights: RecommendationWeights
    limit: int = Field(10, ge=1, le=50)


class HybridRecommendationsRequest(BaseModel):
    userId: int
    weights: HybridWeights = Field(default_factory=HybridWeights)
    limit: int = Field(10, ge=1, le=50)


class ConfigurableRecommendationsRequest(BaseModel):
    userId: int
    weights: ConfigurableWeights = Field(default_factory=ConfigurableWeights)
    limit: int = Field(10, ge=1, le=50)


# ============ Core Endpoints ============

@router.get("/recommendations/{user_id}")
async def get_recommendations(
    user_id: int,
    limit: int = Query(10, ge=1, le=50)
):
    """Get advanced collaborative filtering recommendations for a user.
    
    Uses Jaccard similarity between users (±1.0 rating tolerance) with
    rating-aware prediction and dual-channel normalization (70% min-max, 30% z-score).
    
    Returns: movieId, title, score (0-1), numSimilarUsers, predictedRating
    """
    results = await rec_service.get_collaborative_recommendations(user_id, limit)
    return {
        "userId": user_id,
        "type": "collaborative",
        "algorithm": "Jaccard with rating-aware prediction",
        "recommendations": results
    }


@router.get("/recommendations/{user_id}/content")
async def get_content_recommendations(
    user_id: int,
    limit: int = Query(10, ge=1, le=50)
):
    """Get content-based recommendations for a user.
    
    Builds user profile from movies rated >= 4.0, then recommends movies
    matching genres (60%), actors (30%), and directors (10%).
    
    Returns: movieId, title, totalScore (0-1)
    """
    results = await rec_service.get_content_recommendations(user_id, limit)
    return {
        "userId": user_id,
        "type": "content_based",
        "algorithm": "Weighted Jaccard (genres 0.6, actors 0.3, directors 0.1)",
        "recommendations": results
    }


@router.post("/recommendations/hybrid")
async def get_hybrid_recommendations(payload: HybridRecommendationsRequest):
    """Get hybrid recommendations blending collaborative and content signals.
    
    Combines collaborative (default 0.6) + content (default 0.4) scores with
    boosts for popularity (+5%) and recency (+5%). Applies diversity filter
    ensuring max 3 movies per genre in top-N.
    
    Returns: movieId, title, hybridScore, collaborativeScore, contentScore, genres
    """
    try:
        results = await rec_service.get_hybrid_recommendations(
            user_id=payload.userId,
            collaborative_weight=payload.weights.collaborativeWeight,
            content_weight=payload.weights.contentWeight,
            limit=payload.limit
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {
        "userId": payload.userId,
        "type": "hybrid",
        "algorithm": "Collaborative (Jaccard) + Content (Jaccard) with diversity filter",
        "weights": {
            "collaborative": payload.weights.collaborativeWeight,
            "content": payload.weights.contentWeight,
            "popularity_boost": 0.05,
            "recency_boost": 0.05
        },
        "recommendations": results
    }


@router.post("/recommendations/custom")
async def get_configurable_recommendations(payload: ConfigurableRecommendationsRequest):
    """Get recommendations with fully configurable component weights.
    
    Combines four normalized components:
    - genreScore: Jaccard genre similarity
    - actorScore: Jaccard actor similarity
    - ratingScore: Collaborative predicted rating
    - popularityScore: Quality-weighted popularity
    
    Weights must sum to 1.0. Default distribution: rating (0.45), genre (0.25),
    popularity (0.15), actor (0.15).
    
    Returns: movieId, title, compositeScore, breakdown (with all component scores and weights)
    """
    try:
        results = await rec_service.get_configurable_weight_recommendations(
            user_id=payload.userId,
            genre_weight=payload.weights.genreWeight,
            actor_weight=payload.weights.actorWeight,
            rating_weight=payload.weights.ratingWeight,
            popularity_weight=payload.weights.popularityWeight,
            limit=payload.limit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return {
        "userId": payload.userId,
        "type": "configurable_weighted",
        "algorithm": "Composite with 4 normalized components",
        "weights": {
            "genreWeight": payload.weights.genreWeight,
            "actorWeight": payload.weights.actorWeight,
            "ratingWeight": payload.weights.ratingWeight,
            "popularityWeight": payload.weights.popularityWeight
        },
        "recommendations": results
    }


# ============ Legacy Endpoints (Backward Compatibility) ============

@router.post("/recommendations/custom/legacy")
async def get_custom_recommendations(payload: CustomRecommendationsRequest):
    """Get weighted recommendations with legacy (2-component) algorithm weights.
    
    DEPRECATED: Use /recommendations/hybrid or /recommendations/custom instead.
    
    This endpoint maintains backward compatibility by mapping legacy 'genre'
    and 'rating' weights to the new hybrid model.
    """
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
