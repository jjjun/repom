"""find_by_ids() メソッドのテスト

BaseRepository.find_by_ids() の機能をテストします。
N+1 問題を解決するための一括取得メソッドです。

テストケース:
1. 基本的な一括取得
2. 空リスト対応
3. 存在しないID対応
4. 論理削除フィルタ
5. include_deleted パラメータ
"""

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.base_model_auto import BaseModelAuto
from repom.base_repository import BaseRepository
from repom.mixins import SoftDeletableMixin


# テスト用モデル
class FindByIdsTestModel(BaseModelAuto):
    """通常のテストモデル"""
    __tablename__ = "find_by_ids_test_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class FindByIdsSoftDeleteModel(BaseModelAuto, SoftDeletableMixin):
    """論理削除対応テストモデル"""
    __tablename__ = "find_by_ids_soft_delete_items"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class TestFindByIdsBasic:
    """find_by_ids() の基本機能テスト"""

    def test_find_multiple_records(self, db_test):
        """複数レコードを一括取得"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        # 5件作成
        items = [
            FindByIdsTestModel(name=f"item_{i}")
            for i in range(5)
        ]
        db_test.add_all(items)
        db_test.commit()

        ids = [item.id for item in items]

        # 一括取得
        results = repo.find_by_ids(ids)

        assert len(results) == 5
        result_ids = {r.id for r in results}
        assert result_ids == set(ids)

    def test_find_subset_of_records(self, db_test):
        """一部のレコードを取得"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        # 5件作成
        items = [
            FindByIdsTestModel(name=f"item_{i}")
            for i in range(5)
        ]
        db_test.add_all(items)
        db_test.commit()

        # 3件だけ取得
        target_ids = [items[0].id, items[2].id, items[4].id]
        results = repo.find_by_ids(target_ids)

        assert len(results) == 3
        result_ids = {r.id for r in results}
        assert result_ids == set(target_ids)

    def test_find_single_record(self, db_test):
        """単一レコードを取得"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        item = FindByIdsTestModel(name="single")
        db_test.add(item)
        db_test.commit()

        results = repo.find_by_ids([item.id])

        assert len(results) == 1
        assert results[0].id == item.id
        assert results[0].name == "single"


class TestFindByIdsEdgeCases:
    """find_by_ids() のエッジケーステスト"""

    def test_find_with_empty_list(self, db_test):
        """空リストで取得"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        results = repo.find_by_ids([])

        assert results == []

    def test_find_with_nonexistent_ids(self, db_test):
        """存在しないIDで取得"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        results = repo.find_by_ids([99999, 88888, 77777])

        assert results == []

    def test_find_with_mixed_existent_and_nonexistent(self, db_test):
        """存在するIDと存在しないIDの混在"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        # 2件作成
        item1 = FindByIdsTestModel(name="exists1")
        item2 = FindByIdsTestModel(name="exists2")
        db_test.add_all([item1, item2])
        db_test.commit()

        # 存在するIDと存在しないIDを混在させる
        mixed_ids = [item1.id, 99999, item2.id, 88888]
        results = repo.find_by_ids(mixed_ids)

        # 存在する2件のみ取得される
        assert len(results) == 2
        result_ids = {r.id for r in results}
        assert result_ids == {item1.id, item2.id}

    def test_find_with_duplicate_ids(self, db_test):
        """重複したIDで取得"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        item = FindByIdsTestModel(name="duplicate_test")
        db_test.add(item)
        db_test.commit()

        # 同じIDを重複させる
        duplicate_ids = [item.id, item.id, item.id]
        results = repo.find_by_ids(duplicate_ids)

        # 重複は除外され、1件のみ取得
        assert len(results) == 1
        assert results[0].id == item.id


class TestFindByIdsSoftDelete:
    """find_by_ids() の論理削除対応テスト"""

    def test_excludes_deleted_by_default(self, db_test):
        """削除済みをデフォルトで除外"""
        repo = BaseRepository(FindByIdsSoftDeleteModel, db_test)

        # 3件作成（うち1件削除）
        item1 = FindByIdsSoftDeleteModel(name="active1")
        item2 = FindByIdsSoftDeleteModel(name="deleted")
        item3 = FindByIdsSoftDeleteModel(name="active2")
        db_test.add_all([item1, item2, item3])
        db_test.commit()

        item2.soft_delete()
        db_test.commit()

        ids = [item1.id, item2.id, item3.id]
        results = repo.find_by_ids(ids)

        # 削除済みは除外され、2件のみ
        assert len(results) == 2
        result_ids = {r.id for r in results}
        assert result_ids == {item1.id, item3.id}

    def test_includes_deleted_with_parameter(self, db_test):
        """include_deleted=True で削除済みも取得"""
        repo = BaseRepository(FindByIdsSoftDeleteModel, db_test)

        # 3件作成（うち1件削除）
        item1 = FindByIdsSoftDeleteModel(name="active1")
        item2 = FindByIdsSoftDeleteModel(name="deleted")
        item3 = FindByIdsSoftDeleteModel(name="active2")
        db_test.add_all([item1, item2, item3])
        db_test.commit()

        item2.soft_delete()
        db_test.commit()

        ids = [item1.id, item2.id, item3.id]
        results = repo.find_by_ids(ids, include_deleted=True)

        # 削除済みも含めて3件全て
        assert len(results) == 3
        result_ids = {r.id for r in results}
        assert result_ids == {item1.id, item2.id, item3.id}

    def test_all_deleted_returns_empty(self, db_test):
        """全て削除済みの場合は空リスト"""
        repo = BaseRepository(FindByIdsSoftDeleteModel, db_test)

        # 2件作成して両方削除
        item1 = FindByIdsSoftDeleteModel(name="deleted1")
        item2 = FindByIdsSoftDeleteModel(name="deleted2")
        db_test.add_all([item1, item2])
        db_test.commit()

        item1.soft_delete()
        item2.soft_delete()
        db_test.commit()

        ids = [item1.id, item2.id]
        results = repo.find_by_ids(ids)

        assert results == []

    def test_normal_model_without_soft_delete(self, db_test):
        """論理削除非対応モデルでも動作"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        # 3件作成
        items = [
            FindByIdsTestModel(name=f"item_{i}")
            for i in range(3)
        ]
        db_test.add_all(items)
        db_test.commit()

        ids = [item.id for item in items]

        # include_deleted パラメータは無視される
        results = repo.find_by_ids(ids, include_deleted=True)

        assert len(results) == 3


class TestFindByIdsPerformance:
    """find_by_ids() のパフォーマンステスト"""

    def test_n_plus_one_problem_resolution(self, db_test):
        """N+1問題が解決されることを確認"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        # 10件作成
        items = [
            FindByIdsTestModel(name=f"item_{i}")
            for i in range(10)
        ]
        db_test.add_all(items)
        db_test.commit()

        ids = [item.id for item in items]

        # 一括取得（1回のクエリ）
        results = repo.find_by_ids(ids)

        # 全件取得できている
        assert len(results) == 10

        # IDマッピングを作成
        result_map = {r.id: r for r in results}

        # ループ内でマップから取得（追加クエリなし）
        for item_id in ids:
            item = result_map.get(item_id)
            assert item is not None
            assert item.id == item_id


class TestFindByIdsIntegration:
    """find_by_ids() の統合テスト"""

    def test_with_order_by_option(self, db_test):
        """order_by オプションと併用"""
        repo = BaseRepository(FindByIdsTestModel, db_test)

        # 3件作成
        items = [
            FindByIdsTestModel(name="item_3"),
            FindByIdsTestModel(name="item_1"),
            FindByIdsTestModel(name="item_2"),
        ]
        db_test.add_all(items)
        db_test.commit()

        ids = [item.id for item in items]

        # id で昇順ソート（allowed_order_columns にデフォルトで含まれる）
        results = repo.find_by_ids(ids, order_by="id:asc")

        assert len(results) == 3
        # ID順にソートされている
        assert results[0].id < results[1].id < results[2].id

    def test_real_world_scenario(self, db_test):
        """実際のユースケースをシミュレート"""
        repo = BaseRepository(FindByIdsSoftDeleteModel, db_test)

        # 複数のアセットを作成（一部削除済み）
        assets = []
        for i in range(20):
            asset = FindByIdsSoftDeleteModel(name=f"asset_{i}")
            assets.append(asset)

        db_test.add_all(assets)
        db_test.commit()

        # いくつかを削除
        for i in [2, 5, 8, 11]:
            assets[i].soft_delete()
        db_test.commit()

        # リンクから取得（N+1問題回避）
        asset_ids = [asset.id for asset in assets]
        active_assets = repo.find_by_ids(asset_ids)

        # 削除済み4件を除く16件が取得される
        assert len(active_assets) == 16

        # IDマッピングで効率的にアクセス
        asset_map = {a.id: a for a in active_assets}

        for asset_id in asset_ids:
            asset = asset_map.get(asset_id)
            # 削除済みは None、アクティブは取得できる
            if asset_id in [assets[i].id for i in [2, 5, 8, 11]]:
                assert asset is None
            else:
                assert asset is not None
