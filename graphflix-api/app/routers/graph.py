"""Graph exploration endpoints."""
from fastapi import APIRouter, HTTPException, Query

from app.queries.graph import (
    GET_RECOMMENDATION_EXPLANATION_GRAPH,
    GET_USER_RECOMMENDATION_GRAPH,
)
from app.services.neo4j_service import neo4j_service

router = APIRouter()


@router.get("/graph/user/{user_id}")
async def get_user_graph(
    user_id: int,
    depth: int = Query(2, ge=1, le=3)
):
    """Return a subgraph around a user for interactive graph exploration."""
    rows = await neo4j_service.execute_read(
        GET_USER_RECOMMENDATION_GRAPH,
        {"userId": user_id, "depth": depth}
    )

    if not rows:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    payload = rows[0]
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])

    if not nodes:
        raise HTTPException(status_code=404, detail=f"No graph data found for user {user_id}")

    return {
        "userId": user_id,
        "depth": depth,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "maxNodes": 100,
            "nodeCount": len(nodes),
            "edgeCount": len(edges)
        }
    }


@router.get("/graph/explain/user/{user_id}/movie/{movie_id}")
async def get_recommendation_explanation_graph(
    user_id: int,
    movie_id: int,
    min_rating: float = Query(4.0, ge=0.0, le=5.0),
    max_similar_users: int = Query(6, ge=1, le=15),
    max_support_movies: int = Query(10, ge=1, le=25),
    max_bridge_movies: int = Query(8, ge=1, le=20),
):
    """Return an explanation graph centered on why a movie is recommended to a user."""
    try:
        rows = await neo4j_service.execute_read(
            GET_RECOMMENDATION_EXPLANATION_GRAPH,
            {
                "userId": user_id,
                "movieId": movie_id,
                "minRating": min_rating,
                "maxSimilarUsers": max_similar_users,
                "maxSupportMovies": max_support_movies,
                "maxBridgeMovies": max_bridge_movies,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to build recommendation explanation graph right now.",
        ) from exc

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No explanation graph found for user {user_id} and movie {movie_id}. "
                "Verify both identifiers exist."
            ),
        )

    payload = rows[0]
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])

    if not nodes:
        raise HTTPException(
            status_code=404,
            detail=f"No explanation graph data found for user {user_id} and movie {movie_id}",
        )

    return {
        "mode": "recommendation_explanation",
        "userId": user_id,
        "movieId": movie_id,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "minRating": min_rating,
            "maxSimilarUsers": max_similar_users,
            "maxSupportMovies": max_support_movies,
            "maxBridgeMovies": max_bridge_movies,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        },
    }
