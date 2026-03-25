"""Neo4j service layer for executing queries"""
from typing import List, Dict, Any
from app.database import neo4j_connection

class Neo4jService:
    def __init__(self):
        pass  # Don't get driver here
    
    def _get_driver(self):
        """Get driver lazily"""
        driver = neo4j_connection.get_driver()
        if driver is None:
            raise RuntimeError("Neo4j driver not initialized. Database connection failed.")
        return driver
    
    async def execute_read(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a read query and return results as list of dicts"""
        driver = self._get_driver()
        async with driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records
    
    async def execute_write(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a write query and return results"""
        driver = self._get_driver()
        async with driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records
    
    async def verify_connection(self) -> bool:
        """Verify database connection"""
        try:
            driver = self._get_driver()
            async with driver.session() as session:
                result = await session.run("RETURN 1 AS test")
                data = await result.data()
                return len(data) > 0
        except Exception as e:
            print(f"Connection error: {e}")
            return False

# Singleton instance
neo4j_service = Neo4jService()