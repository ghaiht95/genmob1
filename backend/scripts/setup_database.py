#!/usr/bin/env python3
import asyncio
import logging
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import settings
from backend.models import Base
from backend.database.database import engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def create_database():
    """Create the database if it doesn't exist."""
    # Parse the current database URL to get components
    url_parts = settings.DATABASE_URL.split('/')
    base_url = '/'.join(url_parts[:-1])
    db_name = url_parts[-1]
    
    # Connect to the default 'postgres' database to create our app database
    default_db_url = f"{base_url}/postgres"
    try:
        # Create engine for postgres default db
        temp_engine = create_async_engine(default_db_url, isolation_level="AUTOCOMMIT")
        
        async with temp_engine.connect() as conn:
            # Check if our database exists
            result = await conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
            )
            database_exists = result.scalar() == 1
            
            if not database_exists:
                logger.info(f"Creating database '{db_name}'...")
                await conn.execute(text(f'CREATE DATABASE {db_name}'))
                logger.info(f"Database '{db_name}' created successfully.")
            else:
                logger.info(f"Database '{db_name}' already exists.")
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise

async def setup_schema():
    """Create all tables defined in the models."""
    try:
        logger.info("Creating tables in the database...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise

async def main():
    """Run the database setup process."""
    try:
        await create_database()
        await setup_schema()
        logger.info("Database setup completed successfully.")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 