from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import neo4j_connection
from app.routers import recommendations, movies, users

settings = get_settings()

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lifecycle events
@app.on_event("startup")
async def startup_event():
    """Connect to Neo4j on startup"""
    await neo4j_connection.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close Neo4j connection on shutdown"""
    await neo4j_connection.close()

# Health check
@app.get("/health")
async def health_check():
    from app.services.neo4j_service import neo4j_service
    db_connected = await neo4j_service.verify_connection()
    return {
        "status": "healthy" if db_connected else "unhealthy",
        "database": "connected" if db_connected else "disconnected"
    }

# Include routers
app.include_router(recommendations.router, prefix=settings.API_PREFIX, tags=["recommendations"])
app.include_router(movies.router, prefix=settings.API_PREFIX, tags=["movies"])
app.include_router(users.router, prefix=settings.API_PREFIX, tags=["users"])