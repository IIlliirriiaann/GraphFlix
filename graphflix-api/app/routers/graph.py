"""Graph exploration endpoints."""
from fastapi import APIRouter, HTTPException, Query

from app.queries.graph import GET_USER_RECOMMENDATION_GRAPH
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
