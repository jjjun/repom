"""
Database lifecycle management for both sync and async engines/sessions.

This module provides unified database management through the DatabaseManager class,
supporting both synchronous and asynchronous operations with lazy initialization
and proper lifecycle management.

Example (FastAPI with lifespan):
    >>> from fastapi import FastAPI, Depends
    >>> from repom.database import get_async_db_session, get_lifespan_manager
    >>> 
    >>> app = FastAPI(lifespan=get_lifespan_manager())
    >>> 
    >>> @app.get("/users")
    >>> async def get_users(session: AsyncSession = Depends(get_async_db_session)):
    >>>     result = await session.execute(select(User))
    >>>     return result.scalars().all()

Example (CLI script - sync):
    >>> from repom.database import get_db_transaction
    >>> 
    >>> def main():
    >>>     with get_db_transaction() as session:
    >>>         user = User(name="test")
    >>>         session.add(user)
    >>>         # Auto commit on exit

Example (CLI script - async):
    >>> import asyncio
    >>> from repom.database import get_standalone_async_transaction
    >>> 
    >>> async def main():
    >>>     async with get_standalone_async_transaction() as session:
    >>>         result = await session.execute(select(User))
    >>>         users = result.scalars().all()
    >>> 
    >>> if __name__ == "__main__":
    >>>     asyncio.run(main())
"""

from typing import Optional, AsyncGenerator, Generator, AsyncContextManager, ContextManager, TypeVar, Generic
from contextlib import contextmanager, asynccontextmanager  # Only for DatabaseManager internal use
import asyncio

from sqlalchemy import create_engine, Engine, inspect
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from repom.config import config
from repom.logging import get_logger

logger = get_logger(__name__)


T = TypeVar('T')


class _ContextManagerIterable(Generic[T]):
    """Adapter to allow generator delegation to context managers."""

    def __init__(self, context_manager: ContextManager[T]):
        self._context_manager = context_manager

    def __enter__(self) -> T:
        return self._context_manager.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        return self._context_manager.__exit__(exc_type, exc_value, traceback)

    def __iter__(self) -> Generator[T, None, None]:
        with self._context_manager as value:
            yield value


class _AsyncContextManagerIterable(Generic[T]):
    """Adapter to allow async generator delegation to async context managers."""

    def __init__(self, context_manager: AsyncContextManager[T]):
        self._context_manager = context_manager

    async def __aenter__(self) -> T:
        return await self._context_manager.__aenter__()

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self._context_manager.__aexit__(exc_type, exc_value, traceback)

    def __aiter__(self) -> AsyncGenerator[T, None]:
        async def generator():
            async with self._context_manager as value:
                yield value

        return generator()


# ========================================
# Declarative Base
# ========================================

Base = declarative_base()
"""
SQLAlchemy declarative base for all models.

All ORM models should inherit from this base class.

Example:
    >>> from repom.database import Base
    >>> from sqlalchemy.orm import Mapped, mapped_column
    >>> 
    >>> class User(Base):
    >>>     __tablename__ = 'users'
    >>>     
    >>>     id: Mapped[int] = mapped_column(primary_key=True)
    >>>     name: Mapped[str] = mapped_column(String(100))
"""


# ========================================
# Database Manager
# ========================================

class DatabaseManager:
    """
    Unified database lifecycle manager for sync/async engines and sessions.

    Features:
    - Lazy initialization: Engines are created only when first accessed
    - Lifespan management: Proper cleanup on application shutdown
    - Dual mode: Supports both synchronous and asynchronous operations
    - Session factories: Provides context managers for safe session handling

    Attributes:
        _sync_engine: Cached synchronous engine instance
        _async_engine: Cached asynchronous engine instance
        _sync_session_factory: Cached synchronous session factory
        _async_session_factory: Cached asynchronous session factory
        _lock: Async lock for thread-safe async engine initialization
    """

    def __init__(self):
        """Initialize DatabaseManager with no engines created."""
        self._sync_engine: Optional[Engine] = None
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._lock = asyncio.Lock()

    # ========================================
    # Sync Engine/Session Management
    # ========================================

    def get_sync_engine(self) -> Engine:
        """
        Get or create the synchronous database engine.

        Lazy initialization: The engine is created on first access.

        Returns:
            Engine: SQLAlchemy synchronous engine

        Example:
            >>> from repom.database import get_sync_engine
            >>> engine = get_sync_engine()
            >>> Base.metadata.create_all(bind=engine)
        """
        if self._sync_engine is None:
            self._sync_engine = create_engine(
                config.db_url,
                **config.engine_kwargs
            )
            logger.debug(f"Sync engine created: {config.db_url}")
        return self._sync_engine

    def get_sync_session_factory(self) -> sessionmaker:
        """
        Get or create the synchronous session factory.

        Returns:
            sessionmaker: Factory for creating new sessions
        """
        if self._sync_session_factory is None:
            engine = self.get_sync_engine()
            self._sync_session_factory = sessionmaker(
                bind=engine,
                autocommit=False,
                autoflush=False
            )
        return self._sync_session_factory

    @contextmanager
    def get_sync_session(self) -> Generator[Session, None, None]:
        """
        Get a synchronous database session (context manager).

        The session is automatically closed when the context exits.
        You must manually commit transactions.

        Yields:
            Session: SQLAlchemy synchronous session

        Example:
            >>> with get_db_session() as session:
            >>>     user = session.execute(select(User)).scalar_one()
            >>>     session.commit()
        """
        factory = self.get_sync_session_factory()
        session = factory()
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def get_sync_transaction(self) -> Generator[Session, None, None]:
        """
        Get a synchronous database session with automatic transaction management.

        Automatically commits on success and rolls back on error.
        The session is closed when the context exits.

        Yields:
            Session: SQLAlchemy synchronous session

        Raises:
            Exception: Any exception raised within the context

        Example:
            >>> with get_db_transaction() as session:
            >>>     user = User(name="test")
            >>>     session.add(user)
            >>>     # Auto commit on exit
        """
        factory = self.get_sync_session_factory()
        session = factory()
        try:
            with session.begin():
                yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def get_standalone_sync_transaction(self) -> Generator[Session, None, None]:
        """
        Get a synchronous database session for standalone scripts.

        Automatically disposes the engine on exit, making it suitable for
        CLI tools, batch scripts, and other standalone applications.

        For FastAPI, use get_sync_transaction() with Depends instead.

        Yields:
            Session: SQLAlchemy synchronous session

        Example:
            >>> from repom.database import _db_manager
            >>> 
            >>> def main():
            >>>     with _db_manager.get_standalone_sync_transaction() as session:
            >>>         result = session.execute(select(User))
            >>>         users = result.scalars().all()
            >>> 
            >>> if __name__ == "__main__":
            >>>     main()
        """
        try:
            with self.get_sync_transaction() as session:
                yield session
        finally:
            self.dispose_sync()

    def get_inspector(self):
        """
        Get database inspector for schema introspection.

        Returns:
            Inspector: SQLAlchemy inspector for database metadata

        Example:
            >>> inspector = get_inspector()
            >>> tables = inspector.get_table_names()
            >>> columns = inspector.get_columns('users')
        """
        engine = self.get_sync_engine()
        return inspect(engine)

    def dispose_sync(self):
        """
        Dispose the synchronous engine and clear cached factories.

        This closes all connections in the connection pool.
        Should be called on application shutdown.
        """
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
            self._sync_session_factory = None
            logger.debug("Sync engine disposed")

    # ========================================
    # Async Engine/Session Management
    # ========================================

    async def get_async_engine(self) -> AsyncEngine:
        """
        Get or create the asynchronous database engine.

        Lazy initialization with async lock for thread-safety.

        Returns:
            AsyncEngine: SQLAlchemy asynchronous engine

        Example:
            >>> engine = await get_async_engine()
            >>> async with engine.begin() as conn:
            >>>     await conn.run_sync(Base.metadata.create_all)
        """
        if self._async_engine is None:
            async with self._lock:
                if self._async_engine is None:
                    async_url = self._convert_to_async_uri(config.db_url)
                    self._async_engine = create_async_engine(
                        async_url,
                        **config.engine_kwargs,
                        echo=False
                    )
                    logger.debug(f"Async engine created: {async_url}")
        return self._async_engine

    async def get_async_session_factory(self) -> async_sessionmaker:
        """
        Get or create the asynchronous session factory.

        Returns:
            async_sessionmaker: Factory for creating new async sessions
        """
        if self._async_session_factory is None:
            engine = await self.get_async_engine()
            self._async_session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False
            )
        return self._async_session_factory

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an asynchronous database session (async context manager).

        The session is automatically closed when the context exits.
        Commits on success, rolls back on error.

        Yields:
            AsyncSession: SQLAlchemy asynchronous session

        Example:
            >>> async with get_async_db_session() as session:
            >>>     result = await session.execute(select(User))
            >>>     users = result.scalars().all()
        """
        factory = await self.get_async_session_factory()
        session = factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def get_async_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an asynchronous database session with explicit transaction management.

        Similar to get_async_session but with explicit transaction block.
        Commits on success, rolls back on error.

        Yields:
            AsyncSession: SQLAlchemy asynchronous session

        Example:
            >>> async with get_async_db_transaction() as session:
            >>>     user = User(name="test")
            >>>     session.add(user)
            >>>     # Auto commit on exit
        """
        factory = await self.get_async_session_factory()
        session = factory()
        try:
            async with session.begin():
                yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def get_standalone_async_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an asynchronous database session for standalone scripts.

        Automatically disposes the engine on exit, making it suitable for
        CLI tools, batch scripts, and other standalone applications.

        For FastAPI, use get_async_transaction() with lifespan_context() instead.

        Yields:
            AsyncSession: SQLAlchemy asynchronous session

        Example:
            >>> import asyncio
            >>> from repom.database import _db_manager
            >>> 
            >>> async def main():
            >>>     async with _db_manager.get_standalone_async_transaction() as session:
            >>>         result = await session.execute(select(User))
            >>>         users = result.scalars().all()
            >>> 
            >>> if __name__ == "__main__":
            >>>     asyncio.run(main())
        """
        try:
            async with self.get_async_transaction() as session:
                yield session
        finally:
            await self.dispose_async()

    async def dispose_async(self):
        """
        Dispose the asynchronous engine and clear cached factories.

        This closes all connections in the connection pool.
        Should be called on application shutdown.
        """
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
            self._async_session_factory = None
            logger.debug("Async engine disposed")

    # ========================================
    # Lifecycle Management
    # ========================================

    async def dispose_all(self):
        """
        Dispose both synchronous and asynchronous engines.

        Should be called on application shutdown to clean up all resources.
        """
        self.dispose_sync()
        await self.dispose_async()
        logger.debug("All engines disposed")

    @asynccontextmanager
    async def lifespan_context(self):
        """
        FastAPI lifespan context manager.

        Use this as the lifespan parameter for FastAPI applications
        to ensure proper cleanup on shutdown.

        Yields:
            None

        Example:
            >>> from fastapi import FastAPI
            >>> from repom.database import get_lifespan_manager
            >>> 
            >>> app = FastAPI(lifespan=get_lifespan_manager())
        """
        # Startup: Nothing to do (lazy initialization)
        yield
        # Shutdown: Clean up all resources
        await self.dispose_all()

    # ========================================
    # Helper Methods
    # ========================================

    @staticmethod
    def _convert_to_async_uri(sync_url: str) -> str:
        """
        Convert synchronous database URL to async-compatible URL.

        Uses sqlalchemy.engine.make_url for safe URL parsing and driver name replacement.
        Supports URLs with explicit drivers (e.g., postgresql+psycopg, mysql+pymysql).

        Args:
            sync_url: Synchronous database URL

        Returns:
            str: Async-compatible database URL

        Raises:
            ValueError: If database URL format is not supported

        Examples:
            >>> _convert_to_async_uri('sqlite:///./db.sqlite3')
            'sqlite+aiosqlite:///./db.sqlite3'

            >>> _convert_to_async_uri('postgresql://user:pass@localhost/db')
            'postgresql+asyncpg://user:pass@localhost/db'

            >>> _convert_to_async_uri('postgresql+psycopg://user:pass@localhost/db')
            'postgresql+asyncpg://user:pass@localhost/db'

            >>> _convert_to_async_uri('sqlite+aiosqlite:///./db.sqlite3')
            'sqlite+aiosqlite:///./db.sqlite3' (already async)
        """
        from sqlalchemy.engine import make_url

        url = make_url(sync_url)
        base_driver = url.drivername.split('+')[0]  # Extract base driver (e.g., 'postgresql' from 'postgresql+psycopg')

        # Mapping of base drivers to async drivers
        async_driver_map = {
            'sqlite': 'sqlite+aiosqlite',
            'postgresql': 'postgresql+asyncpg',
            'mysql': 'mysql+aiomysql',
        }

        # Check if already async
        async_drivers = ['sqlite+aiosqlite', 'postgresql+asyncpg', 'mysql+aiomysql']
        if url.drivername in async_drivers:
            return str(url)

        # Convert to async driver
        if base_driver in async_driver_map:
            url = url.set(drivername=async_driver_map[base_driver])
            return str(url)
        else:
            raise ValueError(
                f"Unsupported database URL format: {sync_url}\n"
                f"Supported formats: sqlite://, postgresql://, mysql://"
            )


# ========================================
# Global Instance
# ========================================

_db_manager = DatabaseManager()
"""Global DatabaseManager instance for the application."""


# ========================================
# Public Utility Functions
# ========================================

def convert_to_async_uri(sync_url: str) -> str:
    """
    Convert synchronous database URL to async-compatible URL.

    This is a public wrapper for the internal _convert_to_async_uri method.

    Args:
        sync_url: Synchronous database URL

    Returns:
        str: Async-compatible database URL

    Raises:
        ValueError: If database URL format is not supported

    Examples:
        >>> convert_to_async_uri('sqlite:///./db.sqlite3')
        'sqlite+aiosqlite:///./db.sqlite3'

        >>> convert_to_async_uri('postgresql://user:pass@localhost/db')
        'postgresql+asyncpg://user:pass@localhost/db'
    """
    return DatabaseManager._convert_to_async_uri(sync_url)


# ========================================
# Public API - Sync
# ========================================

def get_sync_engine() -> Engine:
    """
    Get the synchronous database engine.

    Returns:
        Engine: SQLAlchemy synchronous engine
    """
    return _db_manager.get_sync_engine()


def get_db_session() -> Generator[Session, None, None]:
    """
    Get a synchronous database session (for FastAPI Depends).

    Yields:
        Session: SQLAlchemy synchronous session

    Example:
        >>> from fastapi import Depends
        >>> from repom.database import get_db_session
        >>> 
        >>> @app.get("/users")
        >>> def get_users(session: Session = Depends(get_db_session)):
        >>>     result = session.execute(select(User))
        >>>     return result.scalars().all()
    """
    yield from _ContextManagerIterable(_db_manager.get_sync_session())


def get_db_transaction() -> Generator[Session, None, None]:
    """
    Get a synchronous database session with automatic transaction management.

    Yields:
        Session: SQLAlchemy synchronous session with auto-commit/rollback

    Example:
        >>> from fastapi import Depends
        >>> from repom.database import get_db_transaction
        >>> 
        >>> @app.post("/users")
        >>> def create_user(
        >>>     user_data: UserCreate,
        >>>     session: Session = Depends(get_db_transaction)
        >>> ):
        >>>     user = User(**user_data.dict())
        >>>     session.add(user)
        >>>     # Auto commit on exit
        >>>     return user
    """
    yield from _ContextManagerIterable(_db_manager.get_sync_transaction())


def get_standalone_sync_transaction():
    """
    Get a synchronous database session for standalone scripts.

    Automatically disposes the engine on exit, making it suitable for
    CLI tools, batch scripts, and other standalone applications.

    For FastAPI applications, use get_db_transaction() with Depends instead.

    Returns:
        ContextManager[Session]: Context manager that yields Session

    Example:
        >>> from repom.database import get_standalone_sync_transaction
        >>> from sqlalchemy import select
        >>> from your_project.models import User
        >>> 
        >>> def main():
        >>>     with get_standalone_sync_transaction() as session:
        >>>         result = session.execute(select(User).limit(10))
        >>>         users = result.scalars().all()
        >>>         for user in users:
        >>>             print(user.name)
        >>> 
        >>> if __name__ == "__main__":
        >>>     main()
    """
    return _db_manager.get_standalone_sync_transaction()


def get_inspector():
    """
    Get database inspector for schema introspection.

    Returns:
        Inspector: SQLAlchemy inspector
    """
    return _db_manager.get_inspector()


# ========================================
# Public API - Async
# ========================================

async def get_async_engine() -> AsyncEngine:
    """
    Get the asynchronous database engine.

    Returns:
        AsyncEngine: SQLAlchemy asynchronous engine
    """
    return await _db_manager.get_async_engine()


async def get_async_db_session():
    """
    Get an asynchronous database session (for FastAPI Depends).

    Yields:
        AsyncSession: SQLAlchemy asynchronous session

    Example:
        >>> from fastapi import Depends
        >>> from repom.database import get_async_db_session
        >>> 
        >>> @app.get("/users")
        >>> async def get_users(
        >>>     session: AsyncSession = Depends(get_async_db_session)
        >>> ):
        >>>     result = await session.execute(select(User))
        >>>     return result.scalars().all()
    """
    async for session in _AsyncContextManagerIterable(_db_manager.get_async_session()):
        yield session


async def get_async_db_transaction():
    """
    Get an asynchronous database session with explicit transaction management.

    Yields:
        AsyncSession: SQLAlchemy asynchronous session with auto-commit/rollback
    """
    async for session in _AsyncContextManagerIterable(_db_manager.get_async_transaction()):
        yield session


def get_standalone_async_transaction():
    """
    Get an asynchronous database session for standalone scripts.

    Automatically disposes the engine on exit, making it suitable for
    CLI tools, batch scripts, Jupyter notebooks, and other standalone applications.

    For FastAPI applications, use get_async_db_transaction() with
    lifespan_context() instead.

    Returns:
        AsyncContextManager[AsyncSession]: Async context manager that yields AsyncSession

    Example:
        >>> import asyncio
        >>> from repom.database import get_standalone_async_transaction
        >>> from sqlalchemy import select
        >>> from your_project.models import User
        >>> 
        >>> async def main():
        >>>     async with get_standalone_async_transaction() as session:
        >>>         result = await session.execute(select(User).limit(10))
        >>>         users = result.scalars().all()
        >>>         for user in users:
        >>>             print(user.name)
        >>> 
        >>> if __name__ == "__main__":
        >>>     asyncio.run(main())
    """
    return _db_manager.get_standalone_async_transaction()


# ========================================
# Public API - Lifecycle
# ========================================

async def dispose_engines():
    """
    Dispose all database engines.

    Should be called on application shutdown.
    """
    await _db_manager.dispose_all()


def get_lifespan_manager():
    """
    Get FastAPI lifespan context manager.

    Returns:
        AsyncContextManager: Lifespan context manager for FastAPI

    Example:
        >>> from fastapi import FastAPI
        >>> from repom.database import get_lifespan_manager
        >>> 
        >>> app = FastAPI(lifespan=get_lifespan_manager())
    """
    return _db_manager.lifespan_context()


# ========================================
# Exports
# ========================================

__all__ = [
    # Base
    'Base',
    # Manager
    'DatabaseManager',
    # Sync API
    'get_sync_engine',
    'get_db_session',
    'get_db_transaction',
    'get_standalone_sync_transaction',
    'get_inspector',
    # Async API
    'get_async_engine',
    'get_async_db_session',
    'get_async_db_transaction',
    'get_standalone_async_transaction',
    'convert_to_async_uri',
    # Lifecycle
    'dispose_engines',
    'get_lifespan_manager',
]
