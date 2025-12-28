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
from repom.base_model_auto import BaseModelAuto
from repom.repositories import BaseRepository
from repom.mixins import SoftDeletableMixin


# テスト用モデル
class SoftDeleteTestModel(BaseModelAuto, SoftDeletableMixin):
    """論理削除対応テストモデル"""
    __tablename__ = "soft_delete_test_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class NormalTestModel(BaseModelAuto):
    """論理削除非対応テストモデル"""
    __tablename__ = "normal_test_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


# フィクスチャ定義
@pytest.fixture
def setup_soft_delete_item(db_test):
    """論理削除対応モデルの単一アイテム用フィクスチャ

    SoftDeletableMixin の基本機能テスト用。
    各テストで単一のアイテムが必要な場合に使用。

    Returns:
        SoftDeleteTestModel: 保存済みのテストアイテム
    """
    item = SoftDeleteTestModel(name="test")
    db_test.add(item)
    db_test.commit()
    return item


@pytest.fixture
def setup_soft_delete_items(db_test):
    """論理削除対応モデルの複数アイテム用フィクスチャ

    Repository の自動フィルタリングテスト用。
    アクティブと削除済みの両方のアイテムを提供。

    Returns:
        dict: repo, active_item, deleted_item を含む辞書
    """
    repo = BaseRepository(SoftDeleteTestModel, db_test)

    active_item = SoftDeleteTestModel(name="active")
    deleted_item = SoftDeleteTestModel(name="deleted")
    db_test.add_all([active_item, deleted_item])
    db_test.commit()

    deleted_item.soft_delete()
    db_test.commit()

    return {
        'repo': repo,
        'active_item': active_item,
        'deleted_item': deleted_item,
    }


@pytest.fixture
def setup_normal_item(db_test):
    """論理削除非対応モデル用フィクスチャ

    エラーハンドリングテスト用。
    論理削除機能を持たないモデルを提供。

    Returns:
        dict: repo, item を含む辞書
    """
    repo = BaseRepository(NormalTestModel, db_test)
    item = NormalTestModel(name="test")
    db_test.add(item)
    db_test.commit()

    return {
        'repo': repo,
        'item': item,
    }


@pytest.fixture
def setup_soft_delete_repo(db_test):
    """論理削除対応リポジトリのフィクスチャ

    Repository のソフトデリートメソッドテスト用。
    保存済みのアイテムとリポジトリを提供。

    Returns:
        dict: repo, item を含む辞書
    """
    repo = BaseRepository(SoftDeleteTestModel, db_test)
    item = SoftDeleteTestModel(name="test")
    db_test.add(item)
    db_test.commit()

    return {
        'repo': repo,
        'item': item,
    }


class TestSoftDeletableMixin:
    """SoftDeletableMixin の基本機能テスト"""

    def test_initial_state(self, setup_soft_delete_item):
        """初期状態では削除されていない"""
        item = setup_soft_delete_item

        assert item.is_deleted is False
        assert item.deleted_at is None

    def test_soft_delete_sets_deleted_at(self, setup_soft_delete_item):
        """soft_delete() が deleted_at を設定"""
        item = setup_soft_delete_item

        before = datetime.now(timezone.utc)
        item.soft_delete()
        after = datetime.now(timezone.utc)

        assert item.is_deleted is True
        assert item.deleted_at is not None
        assert before <= item.deleted_at <= after

    def test_restore_clears_deleted_at(self, setup_soft_delete_item):
        """restore() が deleted_at をクリア"""
        item = setup_soft_delete_item

        item.soft_delete()
        assert item.is_deleted is True

        item.restore()
        assert item.is_deleted is False
        assert item.deleted_at is None


class TestBaseRepositoryAutoFiltering:
    """BaseRepository の自動フィルタリング機能テスト"""

    def test_find_excludes_deleted_by_default(self, setup_soft_delete_items):
        """find() が削除済みを自動除外"""
        data = setup_soft_delete_items

        results = data['repo'].find()
        assert len(results) == 1
        assert results[0].id == data['active_item'].id

    def test_find_with_include_deleted(self, setup_soft_delete_items):
        """find(include_deleted=True) が全レコード取得"""
        data = setup_soft_delete_items

        results = data['repo'].find(include_deleted=True)
        assert len(results) == 2

    def test_get_by_id_excludes_deleted_by_default(self, setup_soft_delete_items):
        """get_by_id() が削除済みを自動除外"""
        data = setup_soft_delete_items
        deleted_id = data['deleted_item'].id

        result = data['repo'].get_by_id(deleted_id)
        assert result is None

    def test_get_by_id_with_include_deleted(self, setup_soft_delete_items):
        """get_by_id(include_deleted=True) が削除済みも取得"""
        data = setup_soft_delete_items
        deleted_id = data['deleted_item'].id

        result = data['repo'].get_by_id(deleted_id, include_deleted=True)
        assert result is not None
        assert result.id == deleted_id
        assert result.is_deleted is True

    def test_count_excludes_deleted_by_default(self, setup_soft_delete_items):
        """count() はデフォルトで削除済みを除外し、フラグで含められる"""
        data = setup_soft_delete_items

        assert data['repo'].count() == 1
        assert data['repo'].count(include_deleted=True) == 2


class TestRepositorySoftDelete:
    """Repository.soft_delete() メソッドのテスト"""

    def test_soft_delete_marks_as_deleted(self, setup_soft_delete_repo):
        """soft_delete() が正しく論理削除"""
        data = setup_soft_delete_repo
        item_id = data['item'].id

        assert data['repo'].soft_delete(item_id) is True

        # find() では取得できない
        assert data['repo'].get_by_id(item_id) is None

        # include_deleted=True では取得できる
        deleted_item = data['repo'].get_by_id(item_id, include_deleted=True)
        assert deleted_item is not None
        assert deleted_item.is_deleted is True

    def test_soft_delete_returns_false_if_not_found(self, setup_soft_delete_repo):
        """存在しない ID で soft_delete() を呼ぶと False"""
        repo = setup_soft_delete_repo['repo']

        assert repo.soft_delete(99999) is False

    def test_soft_delete_raises_error_on_unsupported_model(self, setup_normal_item):
        """論理削除非対応モデルで ValueError"""
        data = setup_normal_item

        with pytest.raises(ValueError, match="does not support soft delete"):
            data['repo'].soft_delete(data['item'].id)


class TestRepositoryRestore:
    """Repository.restore() メソッドのテスト"""

    def test_restore_recovers_deleted_item(self, setup_soft_delete_repo):
        """restore() が正しく復元"""
        data = setup_soft_delete_repo
        item_id = data['item'].id

        data['repo'].soft_delete(item_id)
        assert data['repo'].restore(item_id) is True

        restored_item = data['repo'].get_by_id(item_id)
        assert restored_item is not None
        assert restored_item.is_deleted is False

    def test_restore_returns_false_if_not_deleted(self, setup_soft_delete_repo):
        """削除されていないレコードで restore() を呼ぶと False"""
        data = setup_soft_delete_repo

        assert data['repo'].restore(data['item'].id) is False

    def test_restore_returns_false_if_not_found(self, setup_soft_delete_repo):
        """存在しない ID で restore() を呼ぶと False"""
        repo = setup_soft_delete_repo['repo']

        assert repo.restore(99999) is False


class TestRepositoryPermanentDelete:
    """Repository.permanent_delete() メソッドのテスト"""

    def test_permanent_delete_removes_from_database(self, setup_soft_delete_repo):
        """permanent_delete() がデータベースから削除"""
        data = setup_soft_delete_repo
        item_id = data['item'].id

        assert data['repo'].permanent_delete(item_id) is True

        # include_deleted=True でも取得できない
        assert data['repo'].get_by_id(item_id, include_deleted=True) is None

    def test_permanent_delete_works_on_soft_deleted(self, setup_soft_delete_repo):
        """論理削除済みレコードも物理削除可能"""
        data = setup_soft_delete_repo
        item_id = data['item'].id

        # 先に論理削除
        data['repo'].soft_delete(item_id)

        # 物理削除
        assert data['repo'].permanent_delete(item_id) is True
        assert data['repo'].get_by_id(item_id, include_deleted=True) is None

    def test_permanent_delete_works_on_normal_model(self, setup_normal_item):
        """論理削除非対応モデルでも物理削除可能"""
        data = setup_normal_item
        item_id = data['item'].id

        assert data['repo'].permanent_delete(item_id) is True
        assert data['repo'].get_by_id(item_id) is None


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
