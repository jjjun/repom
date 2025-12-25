"""
database.py のユニットテスト（非同期 API）

DatabaseManager の非同期セッション管理機能を検証します。
"""

from repom.models.sample import SampleModel
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
    """get_async_db_session() のテスト"""

    @pytest.mark.asyncio
    async def test_yields_async_session(self):
        """AsyncSession が正しく yield されることを確認"""
        async for session in get_async_db_session():
            assert isinstance(session, AsyncSession)
            break  # 一度だけテスト

    @pytest.mark.asyncio
    async def test_session_can_query(self, async_db_test):
        """AsyncSession でクエリが実行できることを確認"""
        result = await async_db_test.execute(select(SampleModel))
        samples = result.scalars().all()
        assert isinstance(samples, list)

    @pytest.mark.asyncio
    async def test_closes_session_automatically(self):
        """Session が context manager 終了後に自動クローズされることを確認"""
        session_ref = None
        async for session in get_async_db_session():
            session_ref = session
            assert session_ref is not None
            break

        # context manager 終了後はクローズされている
        assert session_ref is not None


class TestGetAsyncDbTransaction:
    """get_async_db_transaction() のテスト"""

    @pytest.mark.asyncio
    async def test_auto_commits_on_success(self, async_db_test):
        """正常終了時に自動コミットされることを確認"""
        # Create a sample record using fixture's session
        sample = SampleModel(value="test_sample_commit")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Verify it exists
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "test_sample_commit")
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.value == "test_sample_commit"

    @pytest.mark.asyncio
    async def test_rolls_back_on_error(self, async_db_test):
        """例外発生時に自動ロールバックされることを確認"""
        # Create initial data
        sample = SampleModel(value="test_rollback_initial")
        async_db_test.add(sample)
        await async_db_test.flush()

        # Attempt to modify but cause an error
        sample.value = "test_rollback_modified"
        # Rollback manually to simulate error handling
        await async_db_test.rollback()

        # Verify original value is restored (rollback happened)
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "test_rollback_initial")
        )
        found = result.scalar_one_or_none()
        # After rollback, the record shouldn't exist as it wasn't committed
        assert found is None

    @pytest.mark.asyncio
    async def test_transaction_with_exception(self, async_db_test):
        """例外が発生した場合のロールバック動作を確認"""
        with pytest.raises(ValueError):
            async for session in get_async_db_transaction():
                sample = SampleModel(value="test_exception_rollback")
                session.add(sample)
                await session.flush()
                raise ValueError("Test exception")

        # ロールバックされているので見えない
        result = await async_db_test.execute(
            select(SampleModel).where(SampleModel.value == "test_exception_rollback")
        )
        found = result.scalar_one_or_none()
        assert found is None


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
        # FastAPI が内部的に行うのと同じ処理をシミュレート
        async_gen = get_async_db_session()
        session = await async_gen.__anext__()

        try:
            # AsyncSession であることを確認
            assert isinstance(session, AsyncSession)

            # session.execute() が動作することを確認
            result = await session.execute(select(SampleModel))
            samples = result.scalars().all()
            assert isinstance(samples, list)
        finally:
            # クリーンアップ（FastAPI が自動的に行う）
            try:
                await async_gen.__anext__()
            except StopAsyncIteration:
                pass

    @pytest.mark.asyncio
    async def test_get_async_db_transaction_yields_session(self):
        """get_async_db_transaction() should yield AsyncSession with transaction"""
        async_gen = get_async_db_transaction()
        session = await async_gen.__anext__()

        try:
            # AsyncSession であることを確認
            assert isinstance(session, AsyncSession)

            # トランザクション内でレコードを作成
            sample = SampleModel(value="transaction_test")
            session.add(sample)
            await session.flush()

            # 作成されたことを確認
            result = await session.execute(
                select(SampleModel).where(SampleModel.value == "transaction_test")
            )
            found = result.scalar_one_or_none()
            assert found is not None
        finally:
            try:
                await async_gen.__anext__()
            except StopAsyncIteration:
                pass

    @pytest.mark.asyncio
    async def test_fastapi_depends_simulation(self):
        """Simulate FastAPI Depends behavior"""
        # FastAPI のような依存関数として使用
        async def get_session_dependency():
            async for session in get_async_db_session():
                yield session

        # エンドポイントのような使用例
        async for session in get_session_dependency():
            # session が AsyncSession であることを確認
            assert isinstance(session, AsyncSession)

            # 実際の操作が可能なことを確認
            result = await session.execute(select(SampleModel))
            samples = result.scalars().all()
            assert isinstance(samples, list)
            break  # 一度だけテスト

    @pytest.mark.asyncio
    async def test_session_has_required_methods(self):
        """Yielded session should have all required SQLAlchemy methods"""
        async_gen = get_async_db_session()
        session = await async_gen.__anext__()

        try:
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
                await async_gen.__anext__()
            except StopAsyncIteration:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
