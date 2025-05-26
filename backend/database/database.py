from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker
from config import settings
from typing import AsyncGenerator
from fastapi import Depends
from models import Base

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
    future=True
)

# Create async session factory
async_session_factory = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    """Initialize the database, creating all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as an async generator."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

# Dependency for FastAPI routes
async def get_db():
    """Dependency that provides a database session to FastAPI routes."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

# Helper function for direct session access (non-generator style)
async def create_session() -> AsyncSession:
    """Create and return a new database session directly."""
    return async_session_factory() 