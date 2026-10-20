from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    """DATABASE_URL is a plain postgresql:// URL (shared with the auth service); use asyncpg."""
    return create_async_engine(make_url(database_url).set(drivername="postgresql+asyncpg"))
