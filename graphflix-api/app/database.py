"""Neo4j database connection"""
from neo4j import AsyncGraphDatabase
from app.config import get_settings

settings = get_settings()

class Neo4jConnection:
    def __init__(self):
        self.driver = None
    
    async def connect(self):
        """Initialize Neo4j driver"""
        self.driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        # Verify connectivity
        await self.driver.verify_connectivity()
        print("Connected to Neo4j")
    
    async def close(self):
        """Close Neo4j driver"""
        if self.driver:
            await self.driver.close()
            print("Disconnected from Neo4j")
    
    def get_driver(self):
        """Get Neo4j driver instance"""
        return self.driver

# Global instance
neo4j_connection = Neo4jConnection()