"""Application configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Neo4j connection
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str
    NEO4J_PASSWORD: str
    
    # API settings
    API_TITLE: str = "GraphFlix API"
    API_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()