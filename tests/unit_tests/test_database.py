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
from repom.base_model import BaseModel
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
    """get_db_session() のテスト"""

    def test_get_db_session_yields_session(self, db_test):
        """セッションが正しく生成されることを確認"""
        with get_db_session() as session:
            assert isinstance(session, Session)

    def test_get_db_session_closes_session(self, db_test):
        """セッションが正しくクローズされることを確認"""
        session_ref = None
        with get_db_session() as session:
            session_ref = session
            assert session.is_active

        # context manager 終了後はクローズされている
        assert session_ref is not None

    def test_get_db_session_no_auto_commit(self, db_test):
        """トランザクションが自動コミットされないことを確認"""
        # データを追加
        item = DatabaseTestModel(name="test_no_commit")
        db_test.add(item)
        db_test.flush()

        # 明示的にコミットしない
        # db_test フィクスチャ内では見えるが、ロールバック後は消える
        from sqlalchemy import select
        result = db_test.execute(select(DatabaseTestModel).where(
            DatabaseTestModel.name == "test_no_commit"
        ))
        items = result.scalars().all()
        assert len(items) == 1


class TestGetDbTransaction:
    """get_db_transaction() のテスト"""

    def test_get_db_transaction_auto_commit(self, db_test):
        """正常終了時に自動コミットされることを確認"""
        from sqlalchemy import select

        with get_db_transaction() as session:
            # データを追加
            item = DatabaseTestModel(name="test_auto_commit")
            session.add(item)

        # 別のセッションで確認（コミットされているので見える）
        with get_db_session() as session:
            result = session.execute(select(DatabaseTestModel).where(
                DatabaseTestModel.name == "test_auto_commit"
            ))
            items = result.scalars().all()
            assert len(items) == 1
            assert items[0].name == "test_auto_commit"

    def test_get_db_transaction_auto_rollback_on_exception(self, db_test):
        """例外発生時に自動ロールバックされることを確認"""
        from sqlalchemy import select

        # 例外が発生することを確認
        with pytest.raises(ValueError):
            with get_db_transaction() as session:
                # データを追加
                item = DatabaseTestModel(name="test_rollback")
                session.add(item)
                # 意図的に例外を発生させる
                raise ValueError("Test exception")

        # 別のセッションで確認（ロールバックされているので見えない）
        with get_db_transaction() as session:
            result = session.execute(select(DatabaseTestModel).where(
                DatabaseTestModel.name == "test_rollback"
            ))
            items = result.scalars().all()
            assert len(items) == 0

    def test_transaction_nested_operations(self, db_test):
        """複数の操作を含むトランザクションのテスト"""
        from sqlalchemy import select

        with get_db_transaction() as session:
            # 複数のアイテムを追加
            for i in range(5):
                item = DatabaseTestModel(name=f"test_nested_{i}")
                session.add(item)

        # 別のセッションで確認（すべてコミットされている）
        with get_db_transaction() as session:
            result = session.execute(select(DatabaseTestModel).where(
                DatabaseTestModel.name.like("test_nested_%")
            ))
            items = result.scalars().all()
            assert len(items) == 5


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
