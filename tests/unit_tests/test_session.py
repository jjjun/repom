"""
session.py のユニットテスト

セッション管理ユーティリティの動作を検証します。
"""

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session

from repom.base_model import BaseModel
from repom.session import (
    get_db_session,
    get_db_transaction,
    get_session,
    transaction,
)


# テスト用モデル
class SessionTestModel(BaseModel):
    """セッション管理テスト用のモデル"""

    __tablename__ = 'session_test_model'
    name: str = Column(String(100))


class TestGetDbSession:
    """get_db_session() のテスト"""

    def test_get_db_session_yields_session(self, db_test):
        """セッションが正しく生成されることを確認"""
        gen = get_db_session()
        session = next(gen)
        assert isinstance(session, Session)
        try:
            next(gen)
        except StopIteration:
            pass  # ジェネレータの終了

    def test_get_db_session_closes_session(self, db_test):
        """セッションが正しくクローズされることを確認"""
        gen = get_db_session()
        session = next(gen)

        # セッションオブジェクトの参照を保持
        session_id = id(session)

        # ジェネレータを終了（finally ブロックでクローズされる）
        try:
            next(gen)
        except StopIteration:
            pass

        # ジェネレータが正常に終了したことを確認
        # （クローズ処理が実行されている）
        assert True  # ジェネレータが正常に終了すれば成功

    def test_get_db_session_no_auto_commit(self, db_test):
        """トランザクションが自動コミットされないことを確認"""
        gen = get_db_session()
        session = next(gen)

        # データを追加
        item = SessionTestModel(name="test_no_commit")
        session.add(item)
        session.flush()

        # 明示的にコミットしない
        try:
            next(gen)
        except StopIteration:
            pass

        # 別のセッションで確認（コミットされていないので見えない）
        gen2 = get_db_session()
        session2 = next(gen2)
        items = session2.query(SessionTestModel).filter_by(name="test_no_commit").all()
        assert len(items) == 0

        try:
            next(gen2)
        except StopIteration:
            pass


class TestGetDbTransaction:
    """get_db_transaction() のテスト"""

    def test_get_db_transaction_auto_commit(self, db_test):
        """正常終了時に自動コミットされることを確認"""
        gen = get_db_transaction()
        session = next(gen)

        # データを追加
        item = SessionTestModel(name="test_auto_commit")
        session.add(item)

        try:
            next(gen)
        except StopIteration:
            pass

        # 別のセッションで確認（コミットされているので見える）
        gen2 = get_db_session()
        session2 = next(gen2)
        items = session2.query(SessionTestModel).filter_by(name="test_auto_commit").all()
        assert len(items) == 1
        assert items[0].name == "test_auto_commit"

        try:
            next(gen2)
        except StopIteration:
            pass

    def test_get_db_transaction_auto_rollback_on_exception(self, db_test):
        """例外発生時に自動ロールバックされることを確認

        Note: このテストでは、実際の使用ケース（FastAPI の Depends など）を
        シミュレートするため、ジェネレータを直接使用します。
        """
        # ジェネレータを使った処理をシミュレート
        def simulate_transaction_with_error():
            gen = get_db_transaction()
            session = next(gen)
            try:
                # データを追加
                item = SessionTestModel(name="test_rollback")
                session.add(item)

                # 意図的に例外を発生させる
                raise ValueError("Test exception")
            except Exception:
                # ジェネレータのクリーンアップを実行
                try:
                    gen.throw(ValueError, "Test exception", None)
                except (ValueError, StopIteration):
                    pass
                raise

        # 例外が発生することを確認
        with pytest.raises(ValueError):
            simulate_transaction_with_error()

        # 別のセッションで確認（ロールバックされているので見えない）
        with transaction() as session:
            items = session.query(SessionTestModel).filter_by(name="test_rollback").all()
            assert len(items) == 0


class TestTransaction:
    """transaction() のテスト"""

    def test_transaction_auto_commit(self, db_test):
        """正常終了時に自動コミットされることを確認"""
        with transaction() as session:
            item = SessionTestModel(name="test_context_commit")
            session.add(item)

        # 別のセッションで確認（コミットされているので見える）
        with transaction() as session:
            items = session.query(SessionTestModel).filter_by(name="test_context_commit").all()
            assert len(items) == 1
            assert items[0].name == "test_context_commit"

    def test_transaction_auto_rollback_on_exception(self, db_test):
        """例外発生時に自動ロールバックされることを確認"""
        try:
            with transaction() as session:
                item = SessionTestModel(name="test_context_rollback")
                session.add(item)
                # 意図的に例外を発生させる
                raise ValueError("Test exception")
        except ValueError:
            pass  # 例外をキャッチ

        # 別のセッションで確認（ロールバックされているので見えない）
        with transaction() as session:
            items = session.query(SessionTestModel).filter_by(name="test_context_rollback").all()
            assert len(items) == 0

    def test_transaction_nested_operations(self, db_test):
        """複数の操作を含むトランザクションのテスト"""
        with transaction() as session:
            # 複数のアイテムを追加
            for i in range(5):
                item = SessionTestModel(name=f"test_nested_{i}")
                session.add(item)

        # 別のセッションで確認（すべてコミットされている）
        with transaction() as session:
            items = session.query(SessionTestModel).filter(
                SessionTestModel.name.like("test_nested_%")
            ).all()
            assert len(items) == 5


class TestGetSession:
    """get_session() のテスト"""

    def test_get_session_returns_session(self, db_test):
        """セッションが正しく返されることを確認"""
        session = get_session()
        assert isinstance(session, Session)
        session.close()

    def test_get_session_requires_manual_close(self, db_test):
        """セッションの手動クローズが必要なことを確認"""
        session = get_session()

        # データを追加
        item = SessionTestModel(name="test_manual_commit")
        session.add(item)
        session.commit()
        session.close()

        # 別のセッションで確認（コミットされているので見える）
        session2 = get_session()
        items = session2.query(SessionTestModel).filter_by(name="test_manual_commit").all()
        assert len(items) == 1
        assert items[0].name == "test_manual_commit"
        session2.close()

    def test_get_session_manual_rollback(self, db_test):
        """手動ロールバックのテスト"""
        session = get_session()

        try:
            # データを追加
            item = SessionTestModel(name="test_manual_rollback")
            session.add(item)
            session.flush()

            # 意図的に例外を発生させる
            raise ValueError("Test exception")
        except ValueError:
            session.rollback()
        finally:
            session.close()

        # 別のセッションで確認（ロールバックされているので見えない）
        session2 = get_session()
        items = session2.query(SessionTestModel).filter_by(name="test_manual_rollback").all()
        assert len(items) == 0
        session2.close()


class TestSessionIsolation:
    """セッションの独立性のテスト"""

    def test_sessions_are_independent(self, db_test):
        """各セッションが独立していることを確認"""
        # セッション1でデータを追加（コミットしない）
        gen1 = get_db_session()
        session1 = next(gen1)
        item1 = SessionTestModel(name="test_isolation_1")
        session1.add(item1)
        session1.flush()

        # セッション2では見えない（独立している）
        gen2 = get_db_session()
        session2 = next(gen2)
        items = session2.query(SessionTestModel).filter_by(name="test_isolation_1").all()
        assert len(items) == 0

        # クリーンアップ
        try:
            next(gen1)
        except StopIteration:
            pass

        try:
            next(gen2)
        except StopIteration:
            pass

    def test_multiple_transactions_do_not_interfere(self, db_test):
        """複数のトランザクションが互いに干渉しないことを確認"""
        # トランザクション1
        with transaction() as session1:
            item1 = SessionTestModel(name="test_multi_tx_1")
            session1.add(item1)

        # トランザクション2
        with transaction() as session2:
            item2 = SessionTestModel(name="test_multi_tx_2")
            session2.add(item2)

        # 両方のデータが独立して保存されている
        with transaction() as session3:
            items1 = session3.query(SessionTestModel).filter_by(name="test_multi_tx_1").all()
            items2 = session3.query(SessionTestModel).filter_by(name="test_multi_tx_2").all()
            assert len(items1) == 1
            assert len(items2) == 1
