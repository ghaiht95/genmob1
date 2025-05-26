#!/usr/bin/env python3
import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.database import engine, async_session_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test the connection to the database."""
    try:
        # Print out the database URL (with password masked)
        db_url = settings.DATABASE_URL
        masked_url = db_url.replace('postgres:', '****:') if 'postgres:' in db_url else db_url
        logger.info(f"Testing connection to: {masked_url}")
        
        # Test engine connection
        logger.info("Testing engine connection...")
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            one = result.scalar()
            logger.info(f"Connection test result: {one}")
            
        # Test session creation and query
        logger.info("Testing session operations...")
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT current_database(), current_user"))
            db_name, user = result.first()
            logger.info(f"Connected to database: {db_name} as user: {user}")
            
            # Test table existence
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            ))
            tables = [row[0] for row in result.all()]
            logger.info(f"Found tables: {tables}")
            
        logger.info("Database connection tests completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Error testing database connection: {e}")
        return False

async def main():
    success = await test_database_connection()
    if not success:
        logger.info("Checking for potential configuration issues...")
        
        # Check if PostgreSQL is running (if using localhost)
        if 'localhost' in settings.DATABASE_URL or '127.0.0.1' in settings.DATABASE_URL:
            logger.info("The database URL suggests a local Postgres instance.")
            logger.info("Suggestions:")
            logger.info("1. Make sure PostgreSQL service is running")
            logger.info("2. Check database credentials (username/password)")
            logger.info("3. Verify the database exists")
            
        # Check if using Docker networking
        if 'db:5432' in settings.DATABASE_URL:
            logger.info("The database URL suggests Docker networking (service name 'db').")
            logger.info("Suggestions:")
            logger.info("1. Make sure the database container is running: 'docker-compose ps'")
            logger.info("2. Try connecting from within the app container")
            logger.info("3. Check Docker network connectivity")
            
        logger.info("\nFix suggestions:")
        logger.info("1. Try setting DATABASE_URL to a valid connection string")
        logger.info("   Example: postgresql+asyncpg://postgres:postgres@localhost:5432/myapp")
        logger.info("2. Ensure PostgreSQL is running and accessible")
        logger.info("3. Check that the database 'myapp' exists")
        logger.info("4. If using Docker, ensure both app and db services are running")

if __name__ == "__main__":
    asyncio.run(main()) 