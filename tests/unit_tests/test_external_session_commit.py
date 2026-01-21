"""
外部セッション使用時の commit 動作テスト

Repository が外部セッションと内部セッションを正しく区別し、
適切なタイミングで commit を実行することを確認します。
"""

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column
from repom.models.base_model import BaseModel
from repom.repositories import BaseRepository
from repom.database import _db_manager


class ExternalSessionTestModel(BaseModel):
    """テスト用モデル"""
    __tablename__ = "test_external_session"

    name: Mapped[str] = mapped_column(String(100))


class ExternalSessionTestRepository(BaseRepository[ExternalSessionTestModel]):
    """テスト用リポジトリ"""

    def __init__(self, session=None):
        super().__init__(ExternalSessionTestModel, session)


def test_internal_session_auto_commit(db_test):
    """内部セッション: save() が自動的に commit を実行（後方互換性）"""
    # セッションなしで Repository を初期化
    repo = ExternalSessionTestRepository()

    # インスタンスを保存
    instance = ExternalSessionTestModel(name="internal_test")
    saved = repo.save(instance)

    assert saved.id is not None
    assert saved.name == "internal_test"

    # 別の Repository インスタンスで検証（commit されていることを確認）
    verify_repo = ExternalSessionTestRepository()
    found = verify_repo.get_by("name", "internal_test", single=True)

    assert found is not None
    assert found.name == "internal_test"


def test_external_session_no_auto_commit(db_test):
    """外部セッション: save() が commit を実行しない（新動作）

    外部セッションを渡した場合、Repository は flush のみを実行し、
    commit は呼び出し側（with ブロック終了時）に委ねられることを検証。
    """
    with _db_manager.get_sync_transaction() as session:
        repo = ExternalSessionTestRepository(session)

        # インスタンスを保存（flush のみ、commit しない）
        instance = ExternalSessionTestModel(name="external_test")
        saved = repo.save(instance)

        assert saved.id is not None
        assert saved.name == "external_test"

        # 同じトランザクション内では見える
        stmt = select(ExternalSessionTestModel).where(ExternalSessionTestModel.name == "external_test")
        result = session.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.name == "external_test"

    # with ブロックを抜けた後、新しいセッションでも見える（commit 完了）
    verify_repo = ExternalSessionTestRepository()
    found_after = verify_repo.get_by("name", "external_test", single=True)

    assert found_after is not None
    assert found_after.name == "external_test"


def test_external_session_rollback_on_error(db_test):
    """外部セッション: エラー時に rollback が呼び出し側で制御される"""
    try:
        with _db_manager.get_sync_transaction() as session:
            repo = ExternalSessionTestRepository(session)

            # 正常なインスタンスを保存
            instance1 = ExternalSessionTestModel(name="rollback_test_1")
            repo.save(instance1)

            # 意図的にエラーを発生させる
            raise ValueError("Intentional error for testing")
    except ValueError:
        pass  # エラーを無視

    # rollback されているため、レコードが存在しない
    verify_repo = ExternalSessionTestRepository()
    found = verify_repo.get_by("name", "rollback_test_1", single=True)

    assert found is None


def test_internal_session_saves_with_commit(db_test):
    """内部セッション: saves() が自動的に commit を実行"""
    repo = ExternalSessionTestRepository()

    instances = [
        ExternalSessionTestModel(name="batch_internal_1"),
        ExternalSessionTestModel(name="batch_internal_2"),
        ExternalSessionTestModel(name="batch_internal_3"),
    ]

    repo.saves(instances)

    # 別の Repository インスタンスで検証（commit されていることを確認）
    verify_repo = ExternalSessionTestRepository()
    found = verify_repo.get_by("name", "batch_internal_1", single=True)

    assert found is not None

    # 全件検証
    all_found = verify_repo.find()
    batch_items = [item for item in all_found if item.name.startswith("batch_internal_")]

    assert len(batch_items) == 3


def test_external_session_saves_no_commit(db_test):
    """外部セッション: saves() が commit を実行しない"""
    with _db_manager.get_sync_transaction() as session:
        repo = ExternalSessionTestRepository(session)

        instances = [
            ExternalSessionTestModel(name="batch_external_1"),
            ExternalSessionTestModel(name="batch_external_2"),
        ]

        repo.saves(instances)

        # トランザクション内では見える
        stmt = select(ExternalSessionTestModel).where(ExternalSessionTestModel.name.like("batch_external_%"))
        result = session.execute(stmt)
        found = result.scalars().all()

        assert len(found) == 2

    # with ブロックを抜けた後、commit されている
    verify_repo = ExternalSessionTestRepository()
    all_items = verify_repo.find()
    batch_items = [item for item in all_items if item.name.startswith("batch_external_")]

    assert len(batch_items) == 2


def test_internal_session_remove_with_commit(db_test):
    """内部セッション: remove() が自動的に commit を実行"""
    # テストデータを準備
    repo = ExternalSessionTestRepository()
    instance = ExternalSessionTestModel(name="remove_internal_test")
    saved = repo.save(instance)
    saved_id = saved.id

    # 削除
    repo.remove(saved)

    # 別の Repository インスタンスで検証（削除されていることを確認）
    verify_repo = ExternalSessionTestRepository()
    found = verify_repo.get_by_id(saved_id)

    assert found is None


def test_external_session_remove_no_commit(db_test):
    """外部セッション: remove() が commit を実行しない"""
    # テストデータを準備
    prep_repo = ExternalSessionTestRepository()
    instance = ExternalSessionTestModel(name="remove_external_test")
    saved = prep_repo.save(instance)
    instance_id = saved.id

    with _db_manager.get_sync_transaction() as session:
        repo = ExternalSessionTestRepository(session)

        # インスタンスを再取得して削除
        stmt = select(ExternalSessionTestModel).where(ExternalSessionTestModel.id == instance_id)
        result = session.execute(stmt)
        to_delete = result.scalar_one()

        repo.remove(to_delete)

        # トランザクション内では削除済み
        stmt2 = select(ExternalSessionTestModel).where(ExternalSessionTestModel.id == instance_id)
        result2 = session.execute(stmt2)
        found = result2.scalar_one_or_none()

        assert found is None

    # with ブロックを抜けた後、削除が反映されている
    verify_repo = ExternalSessionTestRepository()
    found_after = verify_repo.get_by_id(instance_id)

    assert found_after is None


def test_multiple_repos_in_one_transaction(db_test):
    """複数の Repository を 1 つのトランザクションで使用"""
    with _db_manager.get_sync_transaction() as session:
        repo = ExternalSessionTestRepository(session)

        # 複数のインスタンスを保存
        instance1 = ExternalSessionTestModel(name="multi_1")
        instance2 = ExternalSessionTestModel(name="multi_2")

        repo.save(instance1)
        repo.save(instance2)

        # トランザクション内では両方見える
        stmt = select(ExternalSessionTestModel).where(ExternalSessionTestModel.name.like("multi_%"))
        result = session.execute(stmt)
        found = result.scalars().all()

        assert len(found) == 2

    # with ブロックを抜けた後、両方 commit されている
    verify_repo = ExternalSessionTestRepository()
    all_items = verify_repo.find()
    multi_items = [item for item in all_items if item.name.startswith("multi_")]

    assert len(multi_items) == 2
