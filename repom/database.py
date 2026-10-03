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

Example (read-only sync session):
    >>> from sqlalchemy import text
    >>> from repom.database import get_reusable_sync_session
    >>> with get_reusable_sync_session() as session:
    ...     value = session.execute(text("SELECT 1")).scalar_one()

Example (read-only async session):
    >>> import asyncio
    >>> from sqlalchemy import text
    >>> from repom.database import get_reusable_async_session
    >>> async def read_value():
    ...     async with get_reusable_async_session() as session:
    ...         result = await session.execute(text("SELECT 1"))
    ...         return result.scalar_one()
    >>> asyncio.run(read_value())

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

from collections.abc import Mapping
from typing import Optional, AsyncGenerator, Generator, ContextManager, AsyncContextManager
from contextlib import contextmanager, asynccontextmanager  # Only for DatabaseManager internal use
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import asyncio
import math
import ssl
import threading

from sqlalchemy import create_engine, Engine, inspect
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from repom.config import _is_local_postgres_host, _postgres_connection_hosts, config
from repom.exec_env import is_prod_exec_env
from repom.logging import get_logger

logger = get_logger(__name__)


_SECRET_QUERY_PARAM_NAMES = frozenset(
    {
        "password",
        "pgpassword",
        "sslpassword",
        "dsn",
        "oauth_client_secret",
        "scram_client_key",
        "scram_server_key",
    }
)

_ASYNCPG_CONNECT_ARGUMENTS = frozenset(
    {
        "dsn",
        "host",
        "port",
        "user",
        "password",
        "passfile",
        "service",
        "servicefile",
        "database",
        "loop",
        "timeout",
        "statement_cache_size",
        "max_cached_statement_lifetime",
        "max_cacheable_statement_size",
        "command_timeout",
        "ssl",
        "direct_tls",
        "connection_class",
        "record_class",
        "server_settings",
        "target_session_attrs",
        "krbsrvname",
        "gsslib",
    }
)

_LIBPQ_ASYNCPG_CONNECT_ARGUMENTS = frozenset(
    {"sslmode", "sslrootcert", "connect_timeout", "application_name"}
)

_ASYNCPG_DSN_OPTIONS = frozenset(
    {
        "sslcert",
        "sslkey",
        "sslpassword",
        "sslcrl",
        "ssl_min_protocol_version",
        "ssl_max_protocol_version",
    }
)

_SQLALCHEMY_ASYNCPG_CONNECT_ARGUMENTS = frozenset(
    {"prepared_statement_cache_size", "prepared_statement_name_func"}
)


def _mask_secret_query_params(url: str) -> str:
    """Mask known secret query parameters in a database URL.

    ``make_url(...).render_as_string(hide_password=True)`` only hides a
    password carried in the URL's userinfo. libpq also accepts passwords,
    private-key passphrases, OAuth client secrets, and SCRAM keys as query
    parameters; those values must be masked separately.
    """
    try:
        parts = urlsplit(url)
        if not parts.query:
            return url

        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        if not any(key.lower() in _SECRET_QUERY_PARAM_NAMES for key, _ in query_pairs):
            return url

        masked_pairs = [
            (key, "***" if key.lower() in _SECRET_QUERY_PARAM_NAMES else value)
            for key, value in query_pairs
        ]
        return urlunsplit(parts._replace(query=urlencode(masked_pairs, safe="*")))
    except (UnicodeError, ValueError):
        return "<invalid database URL>"


def safe_db_url(url: str) -> str:
    """Return a database URL suitable for display or logging."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<invalid database URL>"

    sanitized_url = _mask_secret_query_params(url)
    if sanitized_url == "<invalid database URL>":
        return sanitized_url

    if parts.netloc.count("@") > 1:
        host = parts.netloc.rsplit("@", 1)[1]
        masked_parts = parts._replace(netloc=f"***@{host}")
        return _mask_secret_query_params(urlunsplit(masked_parts))

    try:
        masked = make_url(sanitized_url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database URL>"
    return _mask_secret_query_params(masked)


def _asyncpg_sslmode(connect_args: Mapping) -> Optional[str]:
    """Return the TLS strength of asyncpg's native ``ssl`` argument."""
    value = connect_args["ssl"]
    if isinstance(value, str):
        return value
    if value is True or isinstance(value, ssl.SSLContext):
        return "require"
    return "disable"


def _resolve_postgres_engine_policy(
    db_url: str, engine_kwargs: dict, *, asyncpg: bool = False
) -> tuple[str, dict, Optional[str], tuple[object, ...]]:
    """Resolve TLS mode from asyncpg ssl, connect_args sslmode, then URL sslmode."""
    url = make_url(db_url)
    if url.get_backend_name() not in {"postgres", "postgresql"}:
        return db_url, engine_kwargs, None, ()

    raw_connect_args = engine_kwargs.get("connect_args")
    if raw_connect_args is None:
        connect_args = {}
    elif isinstance(raw_connect_args, Mapping):
        connect_args = dict(raw_connect_args)
    else:
        raise TypeError("connect_args must be a mapping for PostgreSQL")

    if is_prod_exec_env(config.exec_env) and (
        "dsn" in url.query or "dsn" in connect_args
    ):
        raise ValueError(
            "PostgreSQL DSN overrides are not supported in prod because their "
            "destination and TLS options cannot be validated safely"
        )

    hosts = _postgres_connection_hosts(url, connect_args)
    is_remote = any(not _is_local_postgres_host(host) for host in hosts)
    sslmode = (
        _asyncpg_sslmode(connect_args)
        if asyncpg and "ssl" in connect_args
        else connect_args.get("sslmode", url.query.get("sslmode"))
    )

    if (
        is_prod_exec_env(config.exec_env)
        and is_remote
        and not asyncpg
        and "sslmode" in connect_args
        and connect_args["sslmode"] is None
    ):
        raise ValueError(
            "connect_args['sslmode'] cannot be None for a remote PostgreSQL "
            "destination in prod"
        )

    tls = config.postgres_tls_settings_for_url(url, connect_args, sslmode=sslmode)

    if (
        is_prod_exec_env(config.exec_env)
        and is_remote
        and url.query.get("sslmode") is None
        and connect_args.get("sslmode") is None
    ):
        # A raw SQLAlchemy URL with no TLS option otherwise inherits libpq's
        # weaker default. Materialize the validated production default so both
        # drivers receive it.
        query = dict(url.query)
        query["sslmode"] = tls.sslmode
        url = url.set(query=query)
        db_url = url.render_as_string(hide_password=False)

    effective_sslmode = sslmode
    if effective_sslmode is None:
        effective_sslmode = tls.sslmode

    if raw_connect_args is None or connect_args == raw_connect_args:
        resolved_kwargs = engine_kwargs
    else:
        resolved_kwargs = dict(engine_kwargs)
        resolved_kwargs["connect_args"] = connect_args
    return db_url, resolved_kwargs, effective_sslmode, hosts


def _warn_if_prod_sslmode_not_enforced(
    db_url: str, engine_kwargs: dict, *, asyncpg: bool = False
) -> None:
    """Log a warning when a prod PostgreSQL engine resolves to a non-require sslmode.

    The same URL and connect_args resolver used for engine creation supplies the
    destination and TLS mode, so the warning describes the effective connection.
    """
    if not is_prod_exec_env(config.exec_env):
        return

    try:
        _, _, sslmode, hosts = _resolve_postgres_engine_policy(
            db_url, engine_kwargs, asyncpg=asyncpg
        )
    except Exception:
        return
    if sslmode is None or (
        isinstance(sslmode, str)
        and sslmode in {"require", "verify-ca", "verify-full"}
    ):
        return

    if not hosts:
        return
    destination = ", ".join(repr(host) for host in hosts)
    logger.warning(
        f"PostgreSQL sslmode={sslmode!r} in prod for destination "
        f"{destination}; TLS is not enforced for this connection."
    )


async def _run_shielded(awaitable) -> None:
    """Run *awaitable* to completion even if the surrounding task is cancelled.

    Async session cleanup (rollback / commit / close) must always finish so the
    checked-out DB connection is returned to the pool. ``asyncio.CancelledError``
    is a ``BaseException``, so a cancellation delivered while awaiting cleanup
    would otherwise abort it and leak the connection until the process restarts.

    The awaitable is wrapped in ``asyncio.shield`` and awaited in a loop: a
    cancellation of the outer task does not cancel the shielded task, so we keep
    waiting until it finishes. Its result is retrieved even if the task was
    already done when this function started. If cleanup succeeds, any outer
    cancellation is re-raised. If cleanup fails while the caller is cancelled,
    the cleanup failure is raised with that cancellation as its cause; a
    cancellation of the cleanup task itself is propagated.
    """
    task = asyncio.ensure_future(awaitable)
    pending_cancel: Optional[asyncio.CancelledError] = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            if task.done():
                if task.cancelled():
                    # The shielded cleanup itself was cancelled; retrieve it below.
                    break
                # The outer task was cancelled as cleanup completed. Retrieve
                # the task result below before deciding which outcome to raise.
                pending_cancel = exc
                break
            # The outer task was cancelled while cleanup is still running.
            # Remember the cancellation and keep waiting for cleanup to finish.
            pending_cancel = exc
        except BaseException as cleanup_error:
            if pending_cancel is not None:
                raise cleanup_error from pending_cancel
            raise

    try:
        task.result()
    except BaseException as cleanup_error:
        if pending_cancel is not None and not isinstance(
            cleanup_error, asyncio.CancelledError
        ):
            raise cleanup_error from pending_cancel
        raise

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
        _async_disposal_tasks: Async engine disposal tasks still in progress
        _lock: Thread lock guarding lazy engine/session-factory creation and
            disposal, so concurrent callers (e.g. FastAPI's sync Depends
            running in a thread pool) never create more than one engine.
    """

    def __init__(self):
        """Initialize DatabaseManager with no engines created."""
        self._sync_engine: Optional[Engine] = None
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._async_disposal_tasks: set[asyncio.Task[None]] = set()
        self._lock = threading.Lock()

    @contextmanager
    def bind_engine_for_tests(self, engine: Engine | AsyncEngine):
        """Temporarily bind a test engine and restore the previous manager state."""
        if isinstance(engine, AsyncEngine):
            with self._lock:
                previous_engine = self._async_engine
                previous_factory = self._async_session_factory
                self._async_engine = engine
                self._async_session_factory = None
            try:
                yield engine
            finally:
                with self._lock:
                    self._async_engine = previous_engine
                    self._async_session_factory = previous_factory
        elif isinstance(engine, Engine):
            with self._lock:
                previous_engine = self._sync_engine
                previous_factory = self._sync_session_factory
                self._sync_engine = engine
                self._sync_session_factory = None
            try:
                yield engine
            finally:
                with self._lock:
                    self._sync_engine = previous_engine
                    self._sync_session_factory = previous_factory
        else:
            raise TypeError("engine must be a SQLAlchemy Engine or AsyncEngine")

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
            with self._lock:
                if self._sync_engine is None:
                    sync_url, sync_kwargs, _, _ = _resolve_postgres_engine_policy(
                        config.db_url, config.engine_kwargs
                    )
                    self._sync_engine = create_engine(
                        sync_url,
                        **sync_kwargs
                    )
                    _warn_if_prod_sslmode_not_enforced(sync_url, sync_kwargs)
                    logger.debug(f"Sync engine created: {safe_db_url(sync_url)}")
        return self._sync_engine

    def get_sync_session_factory(self) -> sessionmaker:
        """
        Get or create the synchronous session factory.

        Returns:
            sessionmaker: Factory for creating new sessions
        """
        if self._sync_session_factory is None:
            engine = self.get_sync_engine()
            with self._lock:
                if self._sync_session_factory is None:
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
    def get_sync_session_no_commit(self) -> Generator[Session, None, None]:
        """Get a session that closes without committing.

        Closing the session discards any open transaction without expiring loaded
        objects. Their loaded attribute values remain readable after exit; lazy
        loads still require an active session.
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

        For FastAPI, use ``Depends(get_db_transaction, scope="function")`` instead.

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
            with self._lock:
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

        Lazy initialization guarded by a thread lock, since the engine may be
        created from several event loops running on separate threads. The
        created engine is bound to whichever event loop first uses it.

        Returns:
            AsyncEngine: SQLAlchemy asynchronous engine

        Example:
            >>> engine = await get_async_engine()
            >>> async with engine.begin() as conn:
            >>>     await conn.run_sync(Base.metadata.create_all)
        """
        if self._async_engine is None:
            # create_async_engine() does not await, so holding a plain
            # threading.Lock here (instead of asyncio.Lock, which is bound to
            # the event loop that created it and cannot be shared safely
            # across event loops running on different threads) is safe.
            with self._lock:
                if self._async_engine is None:
                    sync_url = config.db_url
                    source_async_url = DatabaseManager._convert_to_async_uri(sync_url)
                    _, (async_url, async_engine_kwargs) = self.resolve_engine_settings(
                        sync_url, config.engine_kwargs
                    )
                    self._async_engine = create_async_engine(
                        async_url,
                        **async_engine_kwargs
                    )
                    _warn_if_prod_sslmode_not_enforced(
                        sync_url, config.engine_kwargs, asyncpg=True
                    )
                    logger.debug(
                        f"Async engine created: {safe_db_url(source_async_url)}"
                    )
        return self._async_engine

    async def get_async_session_factory(self) -> async_sessionmaker:
        """
        Get or create the asynchronous session factory.

        Returns:
            async_sessionmaker: Factory for creating new async sessions
        """
        if self._async_session_factory is None:
            engine = await self.get_async_engine()
            with self._lock:
                if self._async_session_factory is None:
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
    async def get_async_session_no_commit(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async session that closes without committing.

        Closing the session discards any open transaction without expiring loaded
        objects. Their loaded attribute values remain readable after exit; lazy
        loads still require an active session.
        """
        factory = await self.get_async_session_factory()
        session = factory()
        try:
            yield session
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
        Should be called on application shutdown. The engine is detached before
        disposal starts, so a new engine can be created while its predecessor
        closes. Concurrent disposal calls wait for all disposal tasks they see.
        """
        # Detach and register disposal tasks under the lock, then await them only
        # after leaving it so another caller can create or dispose an engine.
        with self._lock:
            engine = self._async_engine
            self._async_engine = None
            self._async_session_factory = None

            if engine is not None:
                task = asyncio.create_task(engine.dispose())
                self._async_disposal_tasks.add(task)
            disposal_tasks = tuple(self._async_disposal_tasks)

        if disposal_tasks:
            try:
                disposal_results = asyncio.gather(
                    *disposal_tasks, return_exceptions=True
                )
                await _run_shielded(disposal_results)
                for result in disposal_results.result():
                    if isinstance(result, BaseException):
                        raise result
            finally:
                with self._lock:
                    self._async_disposal_tasks.difference_update(
                        task for task in disposal_tasks if task.done()
                    )

        if engine is not None:
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
    async def lifespan_context(self, app=None):
        """
        FastAPI lifespan context manager.

        FastAPI/Starlette call the ``lifespan`` callable with the ``app`` and
        use the return value as an async context manager, so ``app`` is
        accepted (and ignored) here for that call signature. The bound method
        also keeps working when called with no arguments, e.g.
        ``async with _db_manager.lifespan_context():``.

        Use ``get_lifespan_manager()`` to obtain the callable to pass as the
        ``lifespan`` parameter for FastAPI applications, to ensure proper
        cleanup on shutdown.

        Args:
            app: The FastAPI/Starlette application (unused). Optional so this
                method can also be called directly with no arguments.

        Yields:
            None

        Example:
            >>> from fastapi import FastAPI
            >>> from repom.database import get_lifespan_manager
            >>> 
            >>> app = FastAPI(lifespan=get_lifespan_manager())
        """
        # Startup: Nothing to do (lazy initialization)
        try:
            yield
        finally:
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
    def _resolve_asyncpg_ssl(sslmode: str, sslrootcert: "Optional[str]"):
        """Mirror libpq's sslmode/sslrootcert semantics for asyncpg's ``ssl`` arg.

        asyncpg has no sslmode/sslrootcert concept of its own: passing it the
        sslmode string reproduces libpq's disable/allow/prefer/require
        behaviour (opportunistic TLS, no certificate verification), while an
        ssl.SSLContext forces TLS and verifies the certificate chain (and,
        optionally, the hostname). libpq only consults sslrootcert to verify
        the chain in require/verify-ca/verify-full, and only checks the
        hostname for verify-full:

        | sslmode + sslrootcert | libpq (sync engine)                              | asyncpg (this mapping)                |
        | ---------------------- | ------------------------------------------------- | -------------------------------------- |
        | disable                | plaintext                                          | "disable" (sslrootcert ignored)        |
        | allow / prefer         | opportunistic TLS, no verification, may fall back  | "allow" / "prefer" (sslrootcert ignored)|
        | require, no rootcert   | TLS required, no verification                      | "require"                              |
        | require + rootcert     | TLS required; chain verified, no hostname check    | SSLContext(check_hostname=False)       |
        | verify-ca, no rootcert | chain verified against default trust store         | "verify-ca"                            |
        | verify-ca + rootcert   | chain verified, no hostname check                  | SSLContext(check_hostname=False)       |
        | verify-full, no rootcert| chain and hostname verified against default store | "verify-full"                          |
        | verify-full + rootcert | chain and hostname verified                        | SSLContext(check_hostname=True)        |

        Without sslrootcert, the sslmode string is passed straight through so
        asyncpg resolves the default root certificate (and, for verify-full,
        the hostname check) itself.

        Args:
            sslmode: One of disable/allow/prefer/require/verify-ca/verify-full.
            sslrootcert: Path to a CA bundle, or None/empty.

        Returns:
            Either the original sslmode string, or an ssl.SSLContext loaded
            with sslrootcert (verify_mode=CERT_REQUIRED by default).
        """
        if sslmode in ("disable", "allow", "prefer") or not sslrootcert:
            return sslmode
        ssl_context = ssl.create_default_context(cafile=sslrootcert)
        ssl_context.check_hostname = sslmode == "verify-full"
        return ssl_context

    @staticmethod
    def _adapt_asyncpg_connect_options(async_url: str, engine_kwargs: dict) -> "tuple[str, dict]":
        """Translate libpq-style options and preserve native asyncpg parameters.

        SQLAlchemy's asyncpg dialect merges the URL query string and connect_args
        straight into ``asyncpg.connect(**kw)``, which has no ``sslmode``,
        ``sslrootcert``, ``connect_timeout`` or ``application_name`` parameters
        and no catch-all ``**kwargs`` - so db_url's ``?sslmode=...`` and
        engine_kwargs's psycopg-style connect_args would otherwise raise
        TypeError on the first async connection. URL values are defaults;
        explicit connect_args override them. Certificate options that asyncpg
        accepts only in its DSN are moved to a DSN, while SQLAlchemy dialect
        options remain in the URL. Conflicting aliases or unsupported options
        raise ValueError. Only the asyncpg driver is affected; other drivers
        are returned unchanged.

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
        supported_query_options = {
            *_ASYNCPG_CONNECT_ARGUMENTS,
            *_LIBPQ_ASYNCPG_CONNECT_ARGUMENTS,
            *_ASYNCPG_DSN_OPTIONS,
            "prepared_statement_cache_size",
        }
        unsupported_query_options = set(query) - supported_query_options
        if unsupported_query_options:
            names = ", ".join(sorted(repr(name) for name in unsupported_query_options))
            raise ValueError(
                f"Unsupported postgresql+asyncpg URL query option(s): {names}"
            )
        if "server_settings" in query:
            raise ValueError(
                "postgresql+asyncpg URL query option 'server_settings' must be "
                "configured as a mapping in connect_args"
            )

        url_sslmode = query.pop("sslmode", None)
        url_sslrootcert = query.pop("sslrootcert", None)
        url_connect_timeout = query.pop("connect_timeout", None)
        url_application_name = query.pop("application_name", None)
        url_dsn_options = {
            name: query.pop(name)
            for name in _ASYNCPG_DSN_OPTIONS
            if name in query
        }
        url = url.set(query=query)

        raw_connect_args = engine_kwargs.get("connect_args")
        if raw_connect_args is None:
            connect_args = {}
        elif isinstance(raw_connect_args, Mapping):
            connect_args = dict(raw_connect_args)
        else:
            raise TypeError("connect_args must be a mapping for postgresql+asyncpg")

        unsupported_options = set(connect_args) - {
            *_ASYNCPG_CONNECT_ARGUMENTS,
            *_LIBPQ_ASYNCPG_CONNECT_ARGUMENTS,
            *_ASYNCPG_DSN_OPTIONS,
            *_SQLALCHEMY_ASYNCPG_CONNECT_ARGUMENTS,
        }
        if unsupported_options:
            names = ", ".join(sorted(repr(name) for name in unsupported_options))
            raise ValueError(
                f"Unsupported postgresql+asyncpg connect_args option(s): {names}"
            )

        ssl_aliases = {
            "sslmode",
            "sslrootcert",
            *_ASYNCPG_DSN_OPTIONS,
        } & set(connect_args)
        if "ssl" in connect_args and ssl_aliases:
            names = ", ".join(sorted(ssl_aliases))
            raise ValueError(
                f"connect_args['ssl'] conflicts with libpq SSL option(s): {names}"
            )

        asyncpg_connect_args = {
            name: value
            for name, value in connect_args.items()
            if name in _ASYNCPG_CONNECT_ARGUMENTS
            and name != "server_settings"
        }

        connect_dsn_options = {
            name: connect_args[name]
            for name in _ASYNCPG_DSN_OPTIONS
            if name in connect_args
        }
        if "ssl" in connect_args:
            if url_dsn_options:
                names = ", ".join(sorted(url_dsn_options))
                raise ValueError(
                    f"connect_args['ssl'] conflicts with asyncpg DSN URL option(s): "
                    f"{names}"
                )
            url_dsn_options = {}
        elif connect_dsn_options:
            url_dsn_options.update(connect_dsn_options)

        if url_dsn_options and "dsn" in connect_args:
            raise ValueError(
                "connect_args['dsn'] cannot be combined with asyncpg DSN URL or "
                "connect_args options"
            )

        if "ssl" not in connect_args:
            sslmode = connect_args.get("sslmode", url_sslmode)
            sslrootcert = connect_args.get("sslrootcert", url_sslrootcert)
            if sslrootcert and sslmode is None:
                raise ValueError(
                    "sslrootcert requires sslmode or a native asyncpg ssl option"
                )
            if url_dsn_options:
                if sslmode is not None:
                    url_dsn_options["sslmode"] = sslmode
                if sslrootcert is not None:
                    url_dsn_options["sslrootcert"] = sslrootcert
                dsn_url = make_url("postgresql://").set(query=url_dsn_options)
                asyncpg_connect_args["dsn"] = dsn_url.render_as_string(
                    hide_password=False
                )
            elif sslmode is not None:
                asyncpg_connect_args["ssl"] = DatabaseManager._resolve_asyncpg_ssl(
                    sslmode, sslrootcert
                )

        timeout_value = None
        has_timeout_value = False
        if "timeout" in connect_args:
            timeout_value = connect_args["timeout"]
            has_timeout_value = True
        elif url_connect_timeout is not None:
            timeout_value = url_connect_timeout
            has_timeout_value = True

        if "connect_timeout" in connect_args:
            connect_timeout = connect_args["connect_timeout"]
            if "timeout" in connect_args:
                try:
                    existing_timeout = float(timeout_value)
                    connect_timeout_value = float(connect_timeout)
                except (TypeError, ValueError, OverflowError) as error:
                    raise ValueError(
                        "connect_timeout and timeout must be numeric values"
                    ) from error
                if existing_timeout != connect_timeout_value:
                    raise ValueError(
                        "connect_args['connect_timeout'] conflicts with "
                        "connect_args['timeout']"
                    )
            timeout_value = connect_timeout
            has_timeout_value = True

        if has_timeout_value and timeout_value is None and "timeout" in connect_args:
            asyncpg_connect_args["timeout"] = None
        elif has_timeout_value:
            try:
                timeout_value = float(timeout_value)
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(
                    "connect_timeout and timeout must be numeric values"
                ) from error
            if not math.isfinite(timeout_value) or timeout_value < 0:
                raise ValueError(
                    "connect_timeout and timeout must be finite, non-negative values"
                )
            asyncpg_connect_args["timeout"] = timeout_value

        server_settings = connect_args.get("server_settings")
        has_server_settings = "server_settings" in connect_args
        if has_server_settings and server_settings is not None:
            if not isinstance(server_settings, Mapping):
                raise TypeError("connect_args['server_settings'] must be a mapping or None")
            server_settings = dict(server_settings)

        application_name = connect_args.get("application_name", url_application_name)
        if application_name is not None:
            if server_settings is None:
                server_settings = {}
            if (
                "application_name" in server_settings
                and server_settings["application_name"] != application_name
                and "application_name" in connect_args
            ):
                raise ValueError(
                    "connect_args['application_name'] conflicts with "
                    "connect_args['server_settings']['application_name']"
                )
            if "application_name" not in server_settings:
                server_settings["application_name"] = application_name
            has_server_settings = True

        for name in _SQLALCHEMY_ASYNCPG_CONNECT_ARGUMENTS:
            if name in connect_args:
                asyncpg_connect_args[name] = connect_args[name]

        if has_server_settings:
            asyncpg_connect_args["server_settings"] = server_settings

        adapted_kwargs = dict(engine_kwargs)
        if asyncpg_connect_args:
            adapted_kwargs["connect_args"] = asyncpg_connect_args
        else:
            adapted_kwargs.pop("connect_args", None)

        return url.render_as_string(hide_password=False), adapted_kwargs

    @staticmethod
    def resolve_engine_settings(
        sync_url: str, engine_kwargs: dict
    ) -> "tuple[tuple[str, dict], tuple[str, dict]]":
        """Derive the (url, kwargs) pairs for the sync and async engines.

        Both the sync and the async engine are ultimately built from the same
        starting point - a sync URL plus a base engine_kwargs dict - but the
        async engine additionally needs driver conversion
        (_convert_to_async_uri) and asyncpg-specific connect_args translation
        (_adapt_asyncpg_connect_options). Centralizing that derivation here
        lets get_async_engine and repom.testing's fixture factories share one
        implementation instead of drifting apart (repom#166).

        Args:
            sync_url: Synchronous database URL.
            engine_kwargs: Base keyword arguments for create_engine (also the
                starting point for create_async_engine, before async-specific
                adaptation).

        Returns:
            tuple[tuple[str, dict], tuple[str, dict]]: ((sync_url,
            sync_kwargs), (async_url, async_kwargs)).
        """
        sync_url, sync_kwargs, _, _ = _resolve_postgres_engine_policy(
            sync_url, engine_kwargs
        )
        async_url = DatabaseManager._convert_to_async_uri(sync_url)
        async_url, async_kwargs = DatabaseManager._adapt_asyncpg_connect_options(
            async_url, sync_kwargs
        )
        _resolve_postgres_engine_policy(sync_url, sync_kwargs, asyncpg=True)
        return (sync_url, sync_kwargs), (async_url, async_kwargs)


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
        >>>     session: Session = Depends(get_db_transaction, scope="function")
        >>> ):
        >>>     user = User(**user_data.model_dump())
        >>>     session.add(user)
        >>>     # Auto commit before the response is sent
        >>>     return user

    For FastAPI write routes, ``scope="function"`` commits before the response
    is sent. It requires FastAPI >= 0.121.0; see the repository session patterns
    guide for the default-scope behavior and StreamingResponse caveat.
    """
    with _db_manager.get_sync_transaction() as session:
        yield session


def get_standalone_sync_transaction():
    """
    Get a synchronous database session for standalone scripts.

    Automatically disposes the engine on exit, making it suitable for
    CLI tools, batch scripts, and other standalone applications.

    For FastAPI applications, use ``Depends(get_db_transaction, scope="function")``
    instead.

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

    For FastAPI applications, use ``Depends(get_db_transaction, scope="function")``.

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


def get_reusable_sync_session() -> ContextManager[Session]:
    """Get a reusable session that never commits and closes on exit.

    Use this for reads or when the caller needs to manage commit boundaries.
    Closing the session discards any open transaction while preserving loaded
    attribute values for use after the context exits. Lazy loads still require
    an active session. Unlike ``get_db_session()``, this is a context manager.
    The FastAPI dependency ``get_db_session()`` also does not commit on exit.
    """
    return _db_manager.get_sync_session_no_commit()


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

    Example:
        >>> from fastapi import Depends
        >>> from repom.database import get_async_db_transaction
        >>>
        >>> @app.post("/users")
        >>> async def create_user(
        >>>     user_data: UserCreate,
        >>>     session: AsyncSession = Depends(
        >>>         get_async_db_transaction, scope="function"
        >>>     ),
        >>> ):
        >>>     user = User(**user_data.model_dump())
        >>>     session.add(user)
        >>>     return user

    For FastAPI write routes, ``scope="function"`` commits before the response
    is sent. It requires FastAPI >= 0.121.0; see the repository session patterns
    guide for the default-scope behavior and StreamingResponse caveat.
    """
    async with _db_manager.get_async_transaction() as session:
        yield session


def get_standalone_async_transaction():
    """
    Get an asynchronous database session for standalone scripts.

    Automatically disposes the engine on exit, making it suitable for
    CLI tools, batch scripts, Jupyter notebooks, and other standalone applications.

    For FastAPI applications, use
    ``Depends(get_async_db_transaction, scope="function")`` instead.

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

    For FastAPI applications, use
    ``Depends(get_async_db_transaction, scope="function")``.

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


def get_reusable_async_session() -> AsyncContextManager[AsyncSession]:
    """Get a reusable async session that never commits and closes on exit.

    Use this for reads or when the caller needs to manage commit boundaries.
    Closing the session discards any open transaction while preserving loaded
    attribute values for use after the context exits. Lazy loads still require
    an active session. Unlike ``get_async_db_session()``, this context manager
    does not commit on exit. The FastAPI dependency ``get_async_db_session()``
    commits on success.
    """
    return _db_manager.get_async_session_no_commit()


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
    Get the FastAPI lifespan callable.

    FastAPI/Starlette call the returned callable with the app instance and
    use the result as an async context manager, so this must return the
    bound method itself - not an already-created context manager (calling an
    ``_AsyncGeneratorContextManager`` instance, which is also a decorator,
    returns a wrapper function rather than entering the context).

    Returns:
        Callable[[Optional[Any]], AsyncContextManager]: Lifespan callable for FastAPI

    Example:
        >>> from fastapi import FastAPI
        >>> from repom.database import get_lifespan_manager
        >>> 
        >>> app = FastAPI(lifespan=get_lifespan_manager())
    """
    return _db_manager.lifespan_context


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
    'get_reusable_sync_session',
    'get_standalone_sync_transaction',
    'get_inspector',
    # Async API
    'get_async_engine',
    'get_async_db_session',
    'get_async_db_transaction',
    'get_reusable_async_transaction',
    'get_reusable_async_session',
    'get_standalone_async_transaction',
    'convert_to_async_uri',
    # Lifecycle
    'dispose_engines',
    'get_lifespan_manager',
]
