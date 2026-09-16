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
    >>> from repom.database import get_reusable_sync_transaction
    >>> 
    >>> def main():
    >>>     with get_reusable_sync_transaction() as session:
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

from typing import Optional, AsyncGenerator, Generator
from contextlib import contextmanager, asynccontextmanager  # Only for DatabaseManager internal use
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import asyncio
import ssl

from sqlalchemy import create_engine, Engine, inspect
from sqlalchemy.engine.url import make_url
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


_PASSWORD_QUERY_PARAM_NAMES = frozenset({"password", "pgpassword"})


def _mask_password_query_params(url: str) -> str:
    """Mask password-like query parameters (e.g. ``?password=`` or ``?pgpassword=``).

    ``make_url(...).render_as_string(hide_password=True)`` only hides a
    password carried in the URL's userinfo; a libpq-style ``password=``/
    ``pgpassword=`` query parameter passes through untouched.
    """
    parts = urlsplit(url)
    if not parts.query:
        return url

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    if not any(key.lower() in _PASSWORD_QUERY_PARAM_NAMES for key, _ in query_pairs):
        return url

    masked_pairs = [
        (key, "***" if key.lower() in _PASSWORD_QUERY_PARAM_NAMES else value)
        for key, value in query_pairs
    ]
    return urlunsplit(parts._replace(query=urlencode(masked_pairs, safe="*")))


def safe_db_url(url: str) -> str:
    """Return a database URL suitable for display or logging."""
    scheme, separator, remainder = url.partition("://")
    if separator:
        credentials, at, host = remainder.rpartition("@")
        if at and credentials.count("@"):
            return _mask_password_query_params(f"{scheme}://***@{host}")

    try:
        masked = make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database URL>"
    return _mask_password_query_params(masked)


def _warn_if_prod_sslmode_not_enforced() -> None:
    """Log a warning when a prod PostgreSQL engine resolves to a non-require sslmode.

    This only happens for a local host - config.postgres_sslmode already
    requires 'require' or stronger in prod for any other host - but operators
    should still be able to see that TLS is not enforced for that connection.
    """
    sslmode = config.postgres_sslmode
    if (
        config.db_type == "postgres"
        and config.exec_env == "prod"
        and sslmode != "require"
        and not sslmode.startswith("verify")
    ):
        logger.warning(
            f"PostgreSQL sslmode={sslmode!r} in prod for host "
            f"{config.postgres.host!r}; TLS is not enforced for this connection."
        )


async def _run_shielded(awaitable) -> None:
    """Run *awaitable* to completion even if the surrounding task is cancelled.

    Async session cleanup (rollback / commit / close) must always finish so the
    checked-out DB connection is returned to the pool. ``asyncio.CancelledError``
    is a ``BaseException``, so a cancellation delivered while awaiting cleanup
    would otherwise abort it and leak the connection until the process restarts.

    The awaitable is wrapped in ``asyncio.shield`` and awaited in a loop: a
    cancellation of the outer task does not cancel the shielded task, so we keep
    waiting until it finishes and then re-raise ``CancelledError`` to preserve
    cancellation semantics.
    """
    task = asyncio.ensure_future(awaitable)
    pending_cancel: Optional[asyncio.CancelledError] = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            if task.done():
                # The shielded cleanup itself was cancelled; propagate.
                raise
            # The outer task was cancelled while cleanup is still running.
            # Remember the cancellation and keep waiting for cleanup to finish.
            pending_cancel = exc
    if pending_cancel is not None:
        raise pending_cancel


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
            _warn_if_prod_sslmode_not_enforced()
            logger.debug(f"Sync engine created: {safe_db_url(config.db_url)}")
        return self._sync_engine

    def get_sync_session_factory(self) -> sessionmaker:
        """
        Get or create the synchronous session factory.

        Returns:
            sessionmaker: Factory for creating new sessions
        """
        if self._sync_session_factory is None:
            engine = self.get_sync_engine()
            # Sync retains SQLAlchemy's expire_on_commit=True default; see
            # AsyncBaseRepository.save() for the async refresh rationale.
            self._sync_session_factory = sessionmaker(
                bind=engine,
                autocommit=False,
                # The inherited False default is documented in the repository guide.
                autoflush=config.autoflush
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
            >>> from repom.database import DatabaseManager
            >>> manager = DatabaseManager()
            >>> with manager.get_sync_session() as session:
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
            >>> from repom.database import DatabaseManager
            >>> manager = DatabaseManager()
            >>> with manager.get_sync_transaction() as session:
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

        For FastAPI, use get_db_transaction() with Depends instead.

        Yields:
            Session: SQLAlchemy synchronous session

        Example:
            >>> from repom.database import DatabaseManager
            >>> manager = DatabaseManager()
            >>> 
            >>> def main():
            >>>     with manager.get_standalone_sync_transaction() as session:
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
                    async_url, async_engine_kwargs = self._adapt_asyncpg_connect_options(
                        async_url, config.engine_kwargs
                    )
                    self._async_engine = create_async_engine(
                        async_url,
                        **async_engine_kwargs,
                        echo=False
                    )
                    _warn_if_prod_sslmode_not_enforced()
                    logger.debug(f"Async engine created: {safe_db_url(async_url)}")
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
                # See AsyncBaseRepository.save() for the async refresh rationale.
                expire_on_commit=False,
                autocommit=False,
                # The inherited False default is documented in the repository guide.
                autoflush=config.autoflush
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
            >>> from repom.database import DatabaseManager
            >>> manager = DatabaseManager()
            >>> async with manager.get_async_session() as session:
            >>>     result = await session.execute(select(User))
            >>>     users = result.scalars().all()
        """
        factory = await self.get_async_session_factory()
        session = factory()
        try:
            yield session
            await _run_shielded(session.commit())
        except BaseException:
            await _run_shielded(session.rollback())
            raise
        finally:
            await _run_shielded(session.close())

    @asynccontextmanager
    async def get_async_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an asynchronous database session with explicit transaction management.

        Similar to get_async_session but with explicit transaction block.
        Commits on success, rolls back on error.

        Yields:
            AsyncSession: SQLAlchemy asynchronous session

        Example:
            >>> from repom.database import DatabaseManager
            >>> manager = DatabaseManager()
            >>> async with manager.get_async_transaction() as session:
            >>>     user = User(name="test")
            >>>     session.add(user)
            >>>     # Auto commit on exit
        """
        factory = await self.get_async_session_factory()
        session = factory()
        try:
            await _run_shielded(session.begin())
            yield session
            await _run_shielded(session.commit())
        except BaseException:
            if session.in_transaction():
                await _run_shielded(session.rollback())
            raise
        finally:
            await _run_shielded(session.close())

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
            >>> from repom.database import DatabaseManager
            >>> manager = DatabaseManager()
            >>> 
            >>> async def main():
            >>>     async with manager.get_standalone_async_transaction() as session:
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
            return url.render_as_string(hide_password=False)

        # Convert to async driver
        if base_driver in async_driver_map:
            url = url.set(drivername=async_driver_map[base_driver])
            return url.render_as_string(hide_password=False)
        else:
            raise ValueError(
                f"Unsupported database URL format: {safe_db_url(sync_url)}\n"
                f"Supported formats: sqlite://, postgresql://, mysql://"
            )

    @staticmethod
    def _adapt_asyncpg_connect_options(async_url: str, engine_kwargs: dict) -> "tuple[str, dict]":
        """Translate libpq-style URL/connect_args into asyncpg's own parameters.

        SQLAlchemy's asyncpg dialect merges the URL query string and connect_args
        straight into ``asyncpg.connect(**kw)``, which has no ``sslmode``,
        ``sslrootcert``, ``connect_timeout`` or ``application_name`` parameters
        and no catch-all ``**kwargs`` - so db_url's ``?sslmode=...`` and
        engine_kwargs's psycopg-style connect_args would otherwise raise
        TypeError on the first async connection. Only the asyncpg driver is
        affected; other drivers are returned unchanged.

        Args:
            async_url: Async database URL (already converted by _convert_to_async_uri)
            engine_kwargs: Keyword arguments destined for create_async_engine

        Returns:
            tuple[str, dict]: (possibly rewritten URL, possibly rewritten kwargs)
        """
        url = make_url(async_url)
        if url.drivername != "postgresql+asyncpg":
            return async_url, engine_kwargs

        query = dict(url.query)
        sslmode = query.pop("sslmode", None)
        sslrootcert = query.pop("sslrootcert", None)
        url = url.set(query=query)

        asyncpg_connect_args = {}
        if sslmode is not None:
            if sslrootcert:
                ssl_context = ssl.create_default_context(cafile=sslrootcert)
                if sslmode == "verify-ca":
                    ssl_context.check_hostname = False
                elif sslmode == "verify-full":
                    ssl_context.check_hostname = True
                asyncpg_connect_args["ssl"] = ssl_context
            else:
                asyncpg_connect_args["ssl"] = sslmode

        connect_args = engine_kwargs.get("connect_args") or {}
        if "connect_timeout" in connect_args:
            asyncpg_connect_args["timeout"] = connect_args["connect_timeout"]
        if "application_name" in connect_args:
            asyncpg_connect_args["server_settings"] = {
                "application_name": connect_args["application_name"]
            }

        adapted_kwargs = dict(engine_kwargs)
        if asyncpg_connect_args:
            adapted_kwargs["connect_args"] = asyncpg_connect_args
        else:
            adapted_kwargs.pop("connect_args", None)

        return url.render_as_string(hide_password=False), adapted_kwargs


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
    with _db_manager.get_sync_session() as session:
        yield session


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
    with _db_manager.get_sync_transaction() as session:
        yield session


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


def get_reusable_sync_transaction():
    """
    Get a reusable synchronous transaction context manager.

    This API is designed for task/worker/CLI code that executes multiple
    transactions within the same process. Unlike
    get_standalone_sync_transaction(), this function does not dispose the
    engine on exit.

    For FastAPI applications, use get_db_transaction() with Depends.

    Returns:
        ContextManager[Session]: Context manager that yields Session

    Example:
        >>> from repom.database import get_reusable_sync_transaction
        >>> from sqlalchemy import select
        >>>
        >>> with get_reusable_sync_transaction() as session:
        >>>     result = session.execute(select(User).limit(10))
        >>>     users = result.scalars().all()
    """
    return _db_manager.get_sync_transaction()


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
    async with _db_manager.get_async_session() as session:
        yield session


async def get_async_db_transaction():
    """
    Get an asynchronous database session with explicit transaction management.

    Yields:
        AsyncSession: SQLAlchemy asynchronous session with auto-commit/rollback
    """
    async with _db_manager.get_async_transaction() as session:
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


def get_reusable_async_transaction():
    """
    Get a reusable asynchronous transaction context manager.

    This API is designed for task/worker/CLI code that executes multiple
    transactions within the same process. Unlike
    get_standalone_async_transaction(), this function does not dispose the
    engine on exit.

    For FastAPI applications, use get_async_db_transaction() with Depends.

    Returns:
        AsyncContextManager[AsyncSession]: Async context manager that yields AsyncSession

    Example:
        >>> from repom.database import get_reusable_async_transaction
        >>> from sqlalchemy import select
        >>>
        >>> async with get_reusable_async_transaction() as session:
        >>>     result = await session.execute(select(User).limit(10))
        >>>     users = result.scalars().all()
    """
    return _db_manager.get_async_transaction()


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
    # Utilities
    'safe_db_url',
    # Manager
    'DatabaseManager',
    # Sync API
    'get_sync_engine',
    'get_db_session',
    'get_db_transaction',
    'get_reusable_sync_transaction',
    'get_standalone_sync_transaction',
    'get_inspector',
    # Async API
    'get_async_engine',
    'get_async_db_session',
    'get_async_db_transaction',
    'get_reusable_async_transaction',
    'get_standalone_async_transaction',
    'convert_to_async_uri',
    # Lifecycle
    'dispose_engines',
    'get_lifespan_manager',
]
