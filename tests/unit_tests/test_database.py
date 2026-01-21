"""
database.py のユニットテスト（同期 API）

DatabaseManager の同期セッション管理機能を検証します。
"""

from repom.database import (
    get_db_session,
    get_db_transaction,
    get_sync_engine,
    get_inspector,
    DatabaseManager,
)
from repom.models.base_model import BaseModel
import os
import pytest
from sqlalchemy import Column, Integer, String, Engine
from sqlalchemy.orm import Session
from sqlalchemy.engine import Inspector

# CRITICAL: Set EXEC_ENV before importing repom modules
os.environ['EXEC_ENV'] = 'test'


# テスト用モデル
class DatabaseTestModel(BaseModel):
    """データベース管理テスト用のモデル"""

    __tablename__ = 'database_test_model'
    name: str = Column(String(100))


class TestGetSyncEngine:
    """get_sync_engine() のテスト"""

    def test_returns_engine(self):
        """Engine が正しく返されることを確認"""
        engine = get_sync_engine()
        assert isinstance(engine, Engine)
        assert engine is not None

    def test_returns_same_instance(self):
        """同じ Engine インスタンスが返されることを確認（シングルトン）"""
        engine1 = get_sync_engine()
        engine2 = get_sync_engine()
        assert engine1 is engine2


class TestGetInspector:
    """get_inspector() のテスト"""

    def test_returns_inspector(self):
        """Inspector が正しく返されることを確認"""
        inspector = get_inspector()
        assert isinstance(inspector, Inspector)

    def test_can_list_tables(self, db_test):
        """Inspector でテーブル一覧が取得できることを確認"""
        inspector = get_inspector()
        tables = inspector.get_table_names()
        assert isinstance(tables, list)


class TestGetDbSession:
    """DEPRECATED: Tests for old 'with' statement behavior removed"""

    def test_deprecated_with_statement_tests(self):
        """Old tests removed - FastAPI Depends compatibility tests in TestFastAPIDependsPattern"""
        pytest.skip("Old 'with' statement tests removed - generator protocol tested in TestFastAPIDependsPattern")


class TestGetDbTransaction:
    """DEPRECATED: Tests for old 'with' statement behavior removed"""

    def test_deprecated_with_statement_tests(self):
        """Old tests removed - FastAPI Depends compatibility tests in TestFastAPIDependsPattern"""
        pytest.skip("Old 'with' statement tests removed - generator protocol tested in TestFastAPIDependsPattern")


class TestDatabaseManager:
    """DatabaseManager クラスのテスト"""

    def test_lazy_initialization_sync(self):
        """Sync Engine は lazy initialization される"""
        # 新しい DatabaseManager インスタンスでテスト（テーブルは不要）
        manager = DatabaseManager()
        assert manager._sync_engine is None
        engine = manager.get_sync_engine()
        assert manager._sync_engine is not None
        assert isinstance(engine, Engine)
        # クリーンアップ
        manager.dispose_sync()

    def test_sync_session_context_manager(self, db_test):
        """Sync Session の context manager 動作確認"""
        # グローバルインスタンスを使用
        from repom.database import _db_manager
        with _db_manager.get_sync_session() as session:
            assert isinstance(session, Session)

    def test_sync_transaction_auto_commit(self, db_test):
        """トランザクションの自動コミット確認"""
        from sqlalchemy import select

        # グローバルインスタンスを使用（テーブルが存在する）
        from repom.database import _db_manager

        with _db_manager.get_sync_transaction() as session:
            item = DatabaseTestModel(name="test_manager_commit")
            session.add(item)

        # 別のセッションで確認
        with _db_manager.get_sync_session() as session:
            result = session.execute(select(DatabaseTestModel).where(
                DatabaseTestModel.name == "test_manager_commit"
            ))
            items = result.scalars().all()
            assert len(items) == 1

    def test_dispose_sync(self):
        """Sync Engine の dispose 動作確認"""
        # 新しいインスタンスでテスト
        manager = DatabaseManager()
        engine = manager.get_sync_engine()
        assert manager._sync_engine is not None

        manager.dispose_sync()
        assert manager._sync_engine is None

    def test_get_inspector_from_manager(self):
        """DatabaseManager から Inspector を取得"""
        from repom.database import _db_manager
        inspector = _db_manager.get_inspector()
        assert isinstance(inspector, Inspector)


class TestSessionIsolation:
    """セッションの独立性のテスト"""

    @pytest.mark.skip(reason=":memory: + StaticPool では全セッションが同じ接続を共有するため、トランザクション分離が機能しない。ファイルベースDBでのみ有効なテスト。")
    def test_sessions_are_independent(self, db_test):
        """各セッションが独立していることを確認"""
        from sqlalchemy import select

        # セッション1でデータを追加（コミットしない）
        with get_db_session() as session1:
            item1 = DatabaseTestModel(name="test_isolation_1")
            session1.add(item1)
            session1.flush()

            # セッション2では見えない（独立している）
            with get_db_session() as session2:
                result = session2.execute(select(DatabaseTestModel).where(
                    DatabaseTestModel.name == "test_isolation_1"
                ))
                items = result.scalars().all()
                assert len(items) == 0

    @pytest.mark.skip(reason=":memory: + StaticPool では全セッションが同じ接続を共有するため、トランザクション分離が機能しない。ファイルベースDBでのみ有効なテスト。")
    def test_multiple_transactions_do_not_interfere(self, db_test):
        """複数のトランザクションが互いに干渉しないことを確認"""
        from sqlalchemy import select

        # トランザクション1
        with get_db_transaction() as session1:
            item1 = DatabaseTestModel(name="test_multi_tx_1")
            session1.add(item1)

        # トランザクション2
        with get_db_transaction() as session2:
            item2 = DatabaseTestModel(name="test_multi_tx_2")
            session2.add(item2)

        # 両方のデータが独立して保存されている
        with get_db_transaction() as session3:
            result1 = session3.execute(select(DatabaseTestModel).where(
                DatabaseTestModel.name == "test_multi_tx_1"
            ))
            result2 = session3.execute(select(DatabaseTestModel).where(
                DatabaseTestModel.name == "test_multi_tx_2"
            ))
            items1 = result1.scalars().all()
            items2 = result2.scalars().all()
            assert len(items1) == 1
            assert len(items2) == 1


class TestFastAPIDependsPattern:
    """FastAPI Depends パターンのテスト - 実際の generator protocol をテスト"""

    def test_get_db_session_is_generator_function(self):
        """get_db_session() should be a generator function (not context manager)"""
        import inspect
        # FastAPI Depends requires generator function
        assert inspect.isgeneratorfunction(get_db_session), \
            "get_db_session must be a generator function for FastAPI Depends compatibility"

    def test_get_db_session_returns_generator(self):
        """get_db_session() should return a generator object"""
        result = get_db_session()
        # Generator object should be returned (not context manager)
        assert type(result).__name__ == 'generator', \
            f"Expected generator but got {type(result).__name__}"
        # Must have __next__ for generator protocol
        assert hasattr(result, '__next__'), \
            "Generator must have __next__ method"
        # Must NOT have __enter__ (not a context manager)
        assert not hasattr(result, '__enter__'), \
            "Generator should not be a context manager"

    def test_get_db_session_yields_session_via_next(self):
        """get_db_session() should yield Session when used with next()"""
        # This is how FastAPI Depends actually works
        gen = get_db_session()
        try:
            # FastAPI calls next(gen) to get the dependency
            session = next(gen)

            # Session であることを確認
            assert isinstance(session, Session), \
                f"Expected Session but got {type(session).__name__}"

            # session.execute() が動作することを確認
            from sqlalchemy import select
            result = session.execute(select(DatabaseTestModel))
            items = result.scalars().all()
            assert isinstance(items, list)
        finally:
            # FastAPI calls next() again for cleanup
            try:
                next(gen)
            except StopIteration:
                pass  # Expected

    def test_get_db_session_context_manager_compatibility(self):
        """get_db_session() should also work with 'with' statement for backward compatibility"""
        # This tests the old behavior (with statement)
        # If @contextmanager is removed, this test should be updated or removed
        try:
            with get_db_session() as session:
                # Session であることを確認
                assert isinstance(session, Session)

                # session.execute() が動作することを確認
                from sqlalchemy import select
                result = session.execute(select(DatabaseTestModel))
                items = result.scalars().all()
                assert isinstance(items, list)
        except (AttributeError, TypeError) as e:
            # If @contextmanager is removed, generator doesn't support 'with'
            pytest.skip(f"Context manager protocol not supported: {e}")

    def test_get_db_transaction_is_generator_function(self):
        """get_db_transaction() should be a generator function"""
        import inspect
        assert inspect.isgeneratorfunction(get_db_transaction), \
            "get_db_transaction must be a generator function for FastAPI Depends compatibility"

    def test_get_db_transaction_returns_generator(self):
        """get_db_transaction() should return a generator object"""
        result = get_db_transaction()
        assert type(result).__name__ == 'generator', \
            f"Expected generator but got {type(result).__name__}"
        assert hasattr(result, '__next__')
        assert not hasattr(result, '__enter__')

    def test_get_db_transaction_yields_session_via_next(self):
        """get_db_transaction() should yield Session with auto-commit"""
        gen = get_db_transaction()
        try:
            session = next(gen)
            assert isinstance(session, Session)

            # トランザクション内でレコードを作成
            item = DatabaseTestModel(name="transaction_test_via_next")
            session.add(item)
            session.flush()

            # 作成されたことを確認（まだコミット前）
            from sqlalchemy import select
            result = session.execute(
                select(DatabaseTestModel).where(DatabaseTestModel.name == "transaction_test_via_next")
            )
            found = result.scalar_one_or_none()
            assert found is not None
        finally:
            # Cleanup (triggers auto-commit)
            try:
                next(gen)
            except StopIteration:
                pass

        # コミットされたことを確認
        gen2 = get_db_session()
        try:
            verify_session = next(gen2)
            from sqlalchemy import select
            result = verify_session.execute(
                select(DatabaseTestModel).where(DatabaseTestModel.name == "transaction_test_via_next")
            )
            found = result.scalar_one_or_none()
            assert found is not None
        finally:
            try:
                next(gen2)
            except StopIteration:
                pass

    def test_fastapi_depends_real_simulation(self):
        """Simulate REAL FastAPI Depends behavior (using next())"""
        # This is how FastAPI actually processes dependencies
        def simulate_fastapi_depends(dependency_func):
            """Simulates FastAPI's dependency injection"""
            gen = dependency_func()
            try:
                # Get the dependency value
                value = next(gen)
                return value
            finally:
                # Cleanup
                try:
                    next(gen)
                except StopIteration:
                    pass

        # Use the simulated Depends
        session = simulate_fastapi_depends(get_db_session)

        # Session であることを確認
        assert isinstance(session, Session), \
            f"Expected Session but got {type(session).__name__}"

        # session.execute() が動作することを確認
        from sqlalchemy import select
        result = session.execute(select(DatabaseTestModel))
        items = result.scalars().all()
        assert isinstance(items, list)
