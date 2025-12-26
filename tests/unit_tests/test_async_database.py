"""
database.py のユニットテスト（非同期 API）

DatabaseManager の非同期セッション管理機能を検証します。
"""

from repom.examples.models.sample import SampleModel
from repom.database import (
    get_async_engine,
    get_async_db_session,
    get_async_db_transaction,
    convert_to_async_uri,
    DatabaseManager,
)
import os
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

# CRITICAL: Set EXEC_ENV before importing repom modules
os.environ['EXEC_ENV'] = 'test'


class TestConvertToAsyncUri:
    """URL 変換機能のテスト"""

    def test_sqlite_url_conversion(self):
        """SQLite URL should be converted to aiosqlite"""
        sync_url = "sqlite:///./database.db"
        async_url = convert_to_async_uri(sync_url)
        assert async_url == "sqlite+aiosqlite:///./database.db"

    def test_postgresql_url_conversion(self):
        """PostgreSQL URL should be converted to asyncpg"""
        sync_url = "postgresql://user:pass@localhost/db"
        async_url = convert_to_async_uri(sync_url)
        assert async_url == "postgresql+asyncpg://user:pass@localhost/db"

    def test_mysql_url_conversion(self):
        """MySQL URL should be converted to aiomysql"""
        sync_url = "mysql://user:pass@localhost/db"
        async_url = convert_to_async_uri(sync_url)
        assert async_url == "mysql+aiomysql://user:pass@localhost/db"

    def test_unsupported_url_raises_error(self):
        """Unsupported database URL should raise ValueError"""
        with pytest.raises(ValueError, match="Unsupported database URL"):
            convert_to_async_uri("unsupported://localhost/db")


class TestGetAsyncEngine:
    """get_async_engine() のテスト"""

    @pytest.mark.asyncio
    async def test_returns_async_engine(self):
        """AsyncEngine が正しく返されることを確認"""
        engine = await get_async_engine()
        assert isinstance(engine, AsyncEngine)
        assert engine is not None

    @pytest.mark.asyncio
    async def test_returns_same_instance(self):
        """同じ AsyncEngine インスタンスが返されることを確認（シングルトン）"""
        engine1 = await get_async_engine()
        engine2 = await get_async_engine()
        assert engine1 is engine2

    @pytest.mark.asyncio
    async def test_async_engine_connection(self):
        """AsyncEngine で接続が作成できることを確認"""
        engine = await get_async_engine()
        async with engine.connect() as conn:
            assert conn is not None


class TestGetAsyncDbSession:
    """DEPRECATED: These tests relied on 'async with' statement which no longer works.

    After removing @asynccontextmanager decorator to fix FastAPI Depends compatibility,
    get_async_db_session() returns an async generator, not a context manager.
    For context manager usage, use DatabaseManager methods directly.
    """

    def test_deprecated_context_manager_usage(self):
        """Skip old tests that used 'async with' statement"""
        pytest.skip(
            "get_async_db_session() no longer supports 'async with' statement. "
            "Use DatabaseManager._db_manager.get_async_session() for context manager usage."
        )


class TestGetAsyncDbTransaction:
    """DEPRECATED: These tests relied on 'async with' statement which no longer works.

    After removing @asynccontextmanager decorator to fix FastAPI Depends compatibility,
    get_async_db_transaction() returns an async generator, not a context manager.
    For context manager usage, use DatabaseManager methods directly.
    """

    def test_deprecated_context_manager_usage(self):
        """Skip old tests that used 'async with' statement"""
        pytest.skip(
            "get_async_db_transaction() no longer supports 'async with' statement. "
            "Use DatabaseManager._db_manager.get_async_transaction() for context manager usage."
        )


class TestDatabaseManager:
    """DatabaseManager クラスの非同期機能テスト"""

    @pytest.mark.asyncio
    async def test_lazy_initialization_async(self):
        """Async Engine は lazy initialization される"""
        manager = DatabaseManager()
        assert manager._async_engine is None
        engine = await manager.get_async_engine()
        assert manager._async_engine is not None
        assert isinstance(engine, AsyncEngine)

    @pytest.mark.asyncio
    async def test_async_session_context_manager(self, async_db_test):
        """Async Session の context manager 動作確認"""
        from repom.database import _db_manager
        async with _db_manager.get_async_session() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_async_transaction_auto_commit(self, async_db_test):
        """トランザクションの自動コミット確認"""
        from repom.database import _db_manager

        async with _db_manager.get_async_transaction() as session:
            item = SampleModel(value="test_manager_async_commit")
            session.add(item)
            await session.flush()

        # 別のセッションで確認
        async with _db_manager.get_async_session() as session:
            result = await session.execute(
                select(SampleModel).where(SampleModel.value == "test_manager_async_commit")
            )
            items = result.scalars().all()
            assert len(items) == 1

    @pytest.mark.asyncio
    async def test_dispose_async(self):
        """Async Engine の dispose 動作確認"""
        manager = DatabaseManager()
        await manager.get_async_engine()
        assert manager._async_engine is not None

        await manager.dispose_async()
        assert manager._async_engine is None

    @pytest.mark.asyncio
    async def test_dispose_all(self):
        """すべての Engine の dispose 動作確認"""
        manager = DatabaseManager()

        # 両方の Engine を作成
        manager.get_sync_engine()
        await manager.get_async_engine()

        assert manager._sync_engine is not None
        assert manager._async_engine is not None

        # すべて破棄
        await manager.dispose_all()

        assert manager._sync_engine is None
        assert manager._async_engine is None


class TestAsyncTransactionIntegration:
    """非同期トランザクションの統合テスト"""

    @pytest.mark.asyncio
    async def test_create_and_query(self, async_db_test):
        """Should be able to create and query records"""
        # Create
        sample = SampleModel(value="async_test")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Query
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "async_test")
        )
        found = result.scalar_one()
        assert found.value == "async_test"

    @pytest.mark.asyncio
    async def test_isolation_between_tests(self, async_db_test):
        """Each test should have isolated transaction"""
        result = await async_db_test.execute(select(SampleModel))
        samples = result.scalars().all()
        assert isinstance(samples, list)

    @pytest.mark.asyncio
    async def test_update_record(self, async_db_test):
        """Should be able to update records"""
        # Create
        sample = SampleModel(value="update_test")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Update
        sample.value = "updated_value"
        await async_db_test.flush()

        # Verify
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "updated_value")
        )
        updated = result.scalar_one()
        assert updated.value == "updated_value"

    @pytest.mark.asyncio
    async def test_delete_record(self, async_db_test):
        """Should be able to delete records"""
        # Create
        sample = SampleModel(value="delete_test")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Delete
        await async_db_test.delete(sample)
        await async_db_test.flush()

        # Verify
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "delete_test")
        )
        deleted = result.scalar_one_or_none()
        assert deleted is None


class TestFastAPIDependsPattern:
    """FastAPI Depends パターンのテスト"""

    @pytest.mark.asyncio
    async def test_get_async_db_session_yields_session(self):
        """get_async_db_session() should yield AsyncSession for FastAPI Depends"""
        # asynccontextmanager デコレータにより、context manager として動作
        async with get_async_db_session() as session:
            # AsyncSession であることを確認
            assert isinstance(session, AsyncSession)

            # session.execute() が動作することを確認
            result = await session.execute(select(SampleModel))
            samples = result.scalars().all()
            assert isinstance(samples, list)


class TestFastAPIDependsPattern:
    """FastAPI Depends パターンのテスト - 実際の async generator protocol をテスト"""

    @pytest.mark.asyncio
    async def test_get_async_db_session_is_async_generator_function(self):
        """get_async_db_session() should be an async generator function"""
        import inspect
        assert inspect.isasyncgenfunction(get_async_db_session), \
            "get_async_db_session must be an async generator function for FastAPI Depends compatibility"

    @pytest.mark.asyncio
    async def test_get_async_db_session_returns_async_generator(self):
        """get_async_db_session() should return an async generator object"""
        result = get_async_db_session()
        # Async generator object should be returned (not context manager)
        assert type(result).__name__ == 'async_generator', \
            f"Expected async_generator but got {type(result).__name__}"
        # Must have __anext__ for async generator protocol
        assert hasattr(result, '__anext__'), \
            "Async generator must have __anext__ method"
        # Must NOT have __aenter__ (not an async context manager)
        assert not hasattr(result, '__aenter__'), \
            "Async generator should not be an async context manager"

    @pytest.mark.asyncio
    async def test_get_async_db_session_yields_session_via_anext(self):
        """get_async_db_session() should yield AsyncSession when used with anext()"""
        # This is how FastAPI Depends actually works with async
        gen = get_async_db_session()
        try:
            # FastAPI calls anext(gen) to get the dependency
            session = await gen.__anext__()

            # AsyncSession であることを確認
            assert isinstance(session, AsyncSession), \
                f"Expected AsyncSession but got {type(session).__name__}"

            # session.execute() が動作することを確認
            result = await session.execute(select(SampleModel))
            items = result.scalars().all()
            assert isinstance(items, list)
        finally:
            # FastAPI calls anext() again for cleanup
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass  # Expected

    @pytest.mark.asyncio
    async def test_get_async_db_session_context_manager_compatibility(self):
        """get_async_db_session() should also work with 'async with' for backward compatibility"""
        # This tests the old behavior (async with statement)
        # If @asynccontextmanager is removed, this test should be updated or removed
        try:
            async with get_async_db_session() as session:
                assert isinstance(session, AsyncSession)
                result = await session.execute(select(SampleModel))
                items = result.scalars().all()
                assert isinstance(items, list)
        except (AttributeError, TypeError) as e:
            # If @asynccontextmanager is removed, async generator doesn't support 'async with'
            pytest.skip(f"Async context manager protocol not supported: {e}")

    @pytest.mark.asyncio
    async def test_get_async_db_transaction_is_async_generator_function(self):
        """get_async_db_transaction() should be an async generator function"""
        import inspect
        assert inspect.isasyncgenfunction(get_async_db_transaction), \
            "get_async_db_transaction must be an async generator function"

    @pytest.mark.asyncio
    async def test_get_async_db_transaction_returns_async_generator(self):
        """get_async_db_transaction() should return an async generator object"""
        result = get_async_db_transaction()
        assert type(result).__name__ == 'async_generator', \
            f"Expected async_generator but got {type(result).__name__}"
        assert hasattr(result, '__anext__')
        assert not hasattr(result, '__aenter__')

    @pytest.mark.asyncio
    async def test_get_async_db_transaction_yields_session_via_anext(self):
        """get_async_db_transaction() should yield AsyncSession with auto-commit"""
        gen = get_async_db_transaction()
        try:
            session = await gen.__anext__()
            assert isinstance(session, AsyncSession)

            # トランザクション内でレコードを作成
            sample = SampleModel(value="transaction_test_via_anext")
            session.add(sample)
            await session.flush()

            # 作成されたことを確認（まだコミット前）
            result = await session.execute(
                select(SampleModel).where(SampleModel.value == "transaction_test_via_anext")
            )
            found = result.scalar_one_or_none()
            assert found is not None
        finally:
            # Cleanup (triggers auto-commit)
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

        # コミットされたことを確認
        gen2 = get_async_db_session()
        try:
            verify_session = await gen2.__anext__()
            result = await verify_session.execute(
                select(SampleModel).where(SampleModel.value == "transaction_test_via_anext")
            )
            found = result.scalar_one_or_none()
            assert found is not None
        finally:
            try:
                await gen2.__anext__()
            except StopAsyncIteration:
                pass

    @pytest.mark.asyncio
    async def test_fastapi_depends_real_simulation(self):
        """Simulate REAL FastAPI Depends behavior (using anext())"""
        # This is how FastAPI actually processes async dependencies
        async def simulate_fastapi_depends(dependency_func):
            """Simulates FastAPI's async dependency injection"""
            gen = dependency_func()
            try:
                # Get the dependency value
                value = await gen.__anext__()
                return value
            finally:
                # Cleanup
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass

        # Use the simulated Depends
        session = await simulate_fastapi_depends(get_async_db_session)

        # AsyncSession であることを確認
        assert isinstance(session, AsyncSession), \
            f"Expected AsyncSession but got {type(session).__name__}"

        # session.execute() が動作することを確認
        result = await session.execute(select(SampleModel))
        items = result.scalars().all()
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_session_has_required_methods(self):
        """Yielded session should have all required SQLAlchemy methods"""
        gen = get_async_db_session()
        try:
            session = await gen.__anext__()

            # 必要なメソッドが存在することを確認
            assert hasattr(session, 'execute')
            assert hasattr(session, 'add')
            assert hasattr(session, 'delete')
            assert hasattr(session, 'commit')
            assert hasattr(session, 'rollback')
            assert hasattr(session, 'flush')
            assert hasattr(session, 'close')

            # execute メソッドが呼び出し可能
            assert callable(session.execute)
        finally:
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
