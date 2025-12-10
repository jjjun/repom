"""論理削除機能のテスト

SoftDeletableMixin と BaseRepository の論理削除機能をテストします。

テストケース:
1. SoftDeletableMixin の基本機能
2. BaseRepository の自動フィルタリング
3. 論理削除・復元・物理削除
4. include_deleted パラメータ
5. 削除済みレコードの検索
6. エラーハンドリング
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model_auto import BaseModelAuto, SoftDeletableMixin
from repom.base_repository import BaseRepository


# テスト用モデル
class SoftDeleteTestModel(BaseModelAuto, SoftDeletableMixin):
    """論理削除対応テストモデル"""
    __tablename__ = "soft_delete_test_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class NormalTestModel(BaseModelAuto):
    """論理削除非対応テストモデル"""
    __tablename__ = "normal_test_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class TestSoftDeletableMixin:
    """SoftDeletableMixin の基本機能テスト"""

    def test_initial_state(self, db_test):
        """初期状態では削除されていない"""
        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()

        assert item.is_deleted is False
        assert item.deleted_at is None

    def test_soft_delete_sets_deleted_at(self, db_test):
        """soft_delete() が deleted_at を設定"""
        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()

        before = datetime.now(timezone.utc)
        item.soft_delete()
        after = datetime.now(timezone.utc)

        assert item.is_deleted is True
        assert item.deleted_at is not None
        assert before <= item.deleted_at <= after

    def test_restore_clears_deleted_at(self, db_test):
        """restore() が deleted_at をクリア"""
        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()

        item.soft_delete()
        assert item.is_deleted is True

        item.restore()
        assert item.is_deleted is False
        assert item.deleted_at is None


class TestBaseRepositoryAutoFiltering:
    """BaseRepository の自動フィルタリング機能テスト"""

    def test_find_excludes_deleted_by_default(self, db_test):
        """find() が削除済みを自動除外"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item1 = SoftDeleteTestModel(name="active")
        item2 = SoftDeleteTestModel(name="deleted")
        db_test.add_all([item1, item2])
        db_test.commit()

        item2.soft_delete()
        db_test.commit()

        results = repo.find()
        assert len(results) == 1
        assert results[0].id == item1.id

    def test_find_with_include_deleted(self, db_test):
        """find(include_deleted=True) が全レコード取得"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item1 = SoftDeleteTestModel(name="active")
        item2 = SoftDeleteTestModel(name="deleted")
        db_test.add_all([item1, item2])
        db_test.commit()

        item2.soft_delete()
        db_test.commit()

        results = repo.find(include_deleted=True)
        assert len(results) == 2

    def test_get_by_id_excludes_deleted_by_default(self, db_test):
        """get_by_id() が削除済みを自動除外"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        item.soft_delete()
        db_test.commit()

        result = repo.get_by_id(item_id)
        assert result is None

    def test_get_by_id_with_include_deleted(self, db_test):
        """get_by_id(include_deleted=True) が削除済みも取得"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        item.soft_delete()
        db_test.commit()

        result = repo.get_by_id(item_id, include_deleted=True)
        assert result is not None
        assert result.id == item_id
        assert result.is_deleted is True


class TestRepositorySoftDelete:
    """Repository.soft_delete() メソッドのテスト"""

    def test_soft_delete_marks_as_deleted(self, db_test):
        """soft_delete() が正しく論理削除"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        assert repo.soft_delete(item_id) is True

        # find() では取得できない
        assert repo.get_by_id(item_id) is None

        # include_deleted=True では取得できる
        deleted_item = repo.get_by_id(item_id, include_deleted=True)
        assert deleted_item is not None
        assert deleted_item.is_deleted is True

    def test_soft_delete_returns_false_if_not_found(self, db_test):
        """存在しない ID で soft_delete() を呼ぶと False"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        assert repo.soft_delete(99999) is False

    def test_soft_delete_raises_error_on_unsupported_model(self, db_test):
        """論理削除非対応モデルで ValueError"""
        repo = BaseRepository(NormalTestModel, db_test)

        item = NormalTestModel(name="test")
        db_test.add(item)
        db_test.commit()

        with pytest.raises(ValueError, match="does not support soft delete"):
            repo.soft_delete(item.id)


class TestRepositoryRestore:
    """Repository.restore() メソッドのテスト"""

    def test_restore_recovers_deleted_item(self, db_test):
        """restore() が正しく復元"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        repo.soft_delete(item_id)
        assert repo.restore(item_id) is True

        restored_item = repo.get_by_id(item_id)
        assert restored_item is not None
        assert restored_item.is_deleted is False

    def test_restore_returns_false_if_not_deleted(self, db_test):
        """削除されていないレコードで restore() を呼ぶと False"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()

        assert repo.restore(item.id) is False

    def test_restore_returns_false_if_not_found(self, db_test):
        """存在しない ID で restore() を呼ぶと False"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        assert repo.restore(99999) is False


class TestRepositoryPermanentDelete:
    """Repository.permanent_delete() メソッドのテスト"""

    def test_permanent_delete_removes_from_database(self, db_test):
        """permanent_delete() がデータベースから削除"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        assert repo.permanent_delete(item_id) is True

        # include_deleted=True でも取得できない
        assert repo.get_by_id(item_id, include_deleted=True) is None

    def test_permanent_delete_works_on_soft_deleted(self, db_test):
        """論理削除済みレコードも物理削除可能"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        # 先に論理削除
        repo.soft_delete(item_id)

        # 物理削除
        assert repo.permanent_delete(item_id) is True
        assert repo.get_by_id(item_id, include_deleted=True) is None

    def test_permanent_delete_works_on_normal_model(self, db_test):
        """論理削除非対応モデルでも物理削除可能"""
        repo = BaseRepository(NormalTestModel, db_test)

        item = NormalTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        assert repo.permanent_delete(item_id) is True
        assert repo.get_by_id(item_id) is None


class TestFindDeleted:
    """find_deleted() と find_deleted_before() のテスト"""

    def test_find_deleted_returns_only_deleted(self, db_test):
        """find_deleted() が削除済みのみ取得"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        active = SoftDeleteTestModel(name="active")
        deleted1 = SoftDeleteTestModel(name="deleted1")
        deleted2 = SoftDeleteTestModel(name="deleted2")
        db_test.add_all([active, deleted1, deleted2])
        db_test.commit()

        deleted1.soft_delete()
        deleted2.soft_delete()
        db_test.commit()

        results = repo.find_deleted()
        assert len(results) == 2
        assert all(item.is_deleted for item in results)

    def test_find_deleted_returns_empty_for_normal_model(self, db_test):
        """論理削除非対応モデルは空リスト"""
        repo = BaseRepository(NormalTestModel, db_test)

        item = NormalTestModel(name="test")
        db_test.add(item)
        db_test.commit()

        results = repo.find_deleted()
        assert len(results) == 0

    def test_find_deleted_before_filters_by_date(self, db_test):
        """find_deleted_before() が日時でフィルタ"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        # 古い削除レコード
        old_item = SoftDeleteTestModel(name="old")
        db_test.add(old_item)
        db_test.commit()
        old_item.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)

        # 新しい削除レコード
        new_item = SoftDeleteTestModel(name="new")
        db_test.add(new_item)
        db_test.commit()
        new_item.soft_delete()

        db_test.commit()

        # 30日以上前に削除されたものを検索
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        old_deleted = repo.find_deleted_before(threshold)

        assert len(old_deleted) == 1
        assert old_deleted[0].id == old_item.id

    def test_find_deleted_before_returns_empty_for_normal_model(self, db_test):
        """論理削除非対応モデルは空リスト"""
        repo = BaseRepository(NormalTestModel, db_test)

        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        results = repo.find_deleted_before(threshold)
        assert len(results) == 0


class TestSoftDeleteIntegration:
    """統合シナリオテスト"""

    def test_complete_lifecycle(self, db_test):
        """作成 → 論理削除 → 復元 → 物理削除のライフサイクル"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        # 作成
        item = SoftDeleteTestModel(name="lifecycle_test")
        db_test.add(item)
        db_test.commit()
        item_id = item.id

        # 通常取得可能
        assert repo.get_by_id(item_id) is not None

        # 論理削除
        repo.soft_delete(item_id)
        assert repo.get_by_id(item_id) is None
        assert repo.get_by_id(item_id, include_deleted=True) is not None

        # 復元
        repo.restore(item_id)
        assert repo.get_by_id(item_id) is not None

        # 物理削除
        repo.permanent_delete(item_id)
        assert repo.get_by_id(item_id, include_deleted=True) is None

    def test_multiple_items_filtering(self, db_test):
        """複数レコードのフィルタリング"""
        repo = BaseRepository(SoftDeleteTestModel, db_test)

        items = [
            SoftDeleteTestModel(name=f"item_{i}")
            for i in range(5)
        ]
        db_test.add_all(items)
        db_test.commit()

        # 2つ削除
        items[1].soft_delete()
        items[3].soft_delete()
        db_test.commit()

        # find() は3つ
        active = repo.find()
        assert len(active) == 3

        # find_deleted() は2つ
        deleted = repo.find_deleted()
        assert len(deleted) == 2

        # find(include_deleted=True) は5つ
        all_items = repo.find(include_deleted=True)
        assert len(all_items) == 5
