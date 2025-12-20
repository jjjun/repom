"""
Async session management for repom.

Provides AsyncSession support for FastAPI and other async frameworks.
Compatible with FastAPI Users, async repositories, and modern async patterns.

Example (FastAPI):
    >>> from fastapi import Depends
    >>> from repom.async_session import get_async_db_session
    >>> 
    >>> @app.get("/users")
    >>> async def get_users(
    >>>     session: AsyncSession = Depends(get_async_db_session)
    >>> ):
    >>>     result = await session.execute(select(User))
    >>>     return result.scalars().all()

Example (FastAPI Users):
    >>> async def get_user_db(
    >>>     session: AsyncSession = Depends(get_async_db_session)
    >>> ):
    >>>     yield SQLAlchemyUserDatabase(session, User)
"""

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from repom.config import config
from repom.logging import get_logger

logger = get_logger(__name__)

# ========================================
# URL Conversion
# ========================================


def convert_to_async_uri(sync_url: str) -> str:
    """Convert synchronous database URL to async-compatible URL.

    Args:
        sync_url: Synchronous database URL

    Returns:
        str: Async-compatible database URL

    Examples:
        >>> convert_to_async_uri('sqlite:///./db.sqlite3')
        'sqlite+aiosqlite:///./db.sqlite3'

        >>> convert_to_async_uri('postgresql://user:pass@localhost/db')
        'postgresql+asyncpg://user:pass@localhost/db'

        >>> convert_to_async_uri('mysql://user:pass@localhost/db')
        'mysql+aiomysql://user:pass@localhost/db'

    Raises:
        ValueError: If database URL format is not supported
    """
    if sync_url.startswith('sqlite'):
        return sync_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    elif sync_url.startswith('postgresql://'):
        return sync_url.replace('postgresql://', 'postgresql+asyncpg://')
    elif sync_url.startswith('mysql://'):
        return sync_url.replace('mysql://', 'mysql+aiomysql://')
    else:
        raise ValueError(
            f"Unsupported database URL format: {sync_url}\n"
            f"Supported formats: sqlite://, postgresql://, mysql://"
        )


# ========================================
# Async Engine
# ========================================

# Create async engine
async_db_url = convert_to_async_uri(config.db_url)
async_engine: AsyncEngine = create_async_engine(
    async_db_url,
    **config.engine_kwargs,
    echo=False
)

logger.debug(f"Async engine created: {async_db_url}")

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# ========================================
# Session Management Functions
# ========================================


async def get_async_session() -> AsyncSession:
    """Get a new AsyncSession instance.

    Returns:
        AsyncSession: A new async SQLAlchemy session

    Note:
        You must call `await session.close()` after use.

    Example:
        >>> session = await get_async_session()
        >>> try:
        >>>     result = await session.execute(select(User))
        >>>     await session.commit()
        >>> finally:
        >>>     await session.close()
    """
    return AsyncSessionLocal()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get AsyncSession with automatic transaction management.

    Designed for use with FastAPI's Depends.
    Automatically commits on success, rolls back on error, and closes the session.

    Yields:
        AsyncSession: Async SQLAlchemy session

    Example (FastAPI):
        >>> from fastapi import Depends
        >>> from repom.async_session import get_async_db_session
        >>> 
        >>> @app.get("/users")
        >>> async def get_users(
        >>>     session: AsyncSession = Depends(get_async_db_session)
        >>> ):
        >>>     result = await session.execute(select(User))
        >>>     return result.scalars().all()

    Example (FastAPI Users):
        >>> from fastapi_users.db import SQLAlchemyUserDatabase
        >>> 
        >>> async def get_user_db(
        >>>     session: AsyncSession = Depends(get_async_db_session)
        >>> ):
        >>>     yield SQLAlchemyUserDatabase(session, User)
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


__all__ = [
    'async_engine',
    'AsyncSessionLocal',
    'get_async_session',
    'get_async_db_session',
    'convert_to_async_uri'
]
