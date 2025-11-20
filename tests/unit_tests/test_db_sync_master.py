"""
db_sync_master のテスト

マスターデータ同期機能のテスト：
- ファイル読み込み
- Upsert ロジック（INSERT / UPDATE）
- トランザクションロールバック
- エラーハンドリング
"""

import os
import pytest
from pathlib import Path
from repom.scripts.db_sync_master import load_master_data_files, sync_master_data
from repom.models.sample import SampleModel
from repom.base_repository import BaseRepository


class TestLoadMasterDataFiles:
    """マスターデータファイル読み込みのテスト"""

    def test_load_master_data_files_success(self, tmp_path):
        """正常なマスターデータファイルの読み込み"""
        # テスト用のマスターデータファイルを作成
        master_file = tmp_path / "001_test.py"
        master_file.write_text(
            """
from repom.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = [
    {"id": 1, "value": "test1"},
    {"id": 2, "value": "test2"},
]
"""
        )

        # ファイルを読み込み
        results = list(load_master_data_files(str(tmp_path)))

        assert len(results) == 1
        model_class, master_data = results[0]
        assert model_class == SampleModel
        assert len(master_data) == 2
        assert master_data[0]["id"] == 1
        assert master_data[1]["value"] == "test2"

    def test_load_master_data_files_multiple_files(self, tmp_path):
        """複数ファイルの読み込み（ソート順序確認）"""
        # ファイルを逆順で作成
        file2 = tmp_path / "002_second.py"
        file2.write_text(
            """
from repom.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = [{"id": 2, "value": "second"}]
"""
        )

        file1 = tmp_path / "001_first.py"
        file1.write_text(
            """
from repom.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = [{"id": 1, "value": "first"}]
"""
        )

        # ソート順に読み込まれるか確認
        results = list(load_master_data_files(str(tmp_path)))
        assert len(results) == 2
        assert results[0][1][0]["value"] == "first"
        assert results[1][1][0]["value"] == "second"

    def test_load_master_data_files_no_directory(self):
        """存在しないディレクトリ"""
        with pytest.raises(FileNotFoundError):
            list(load_master_data_files("/nonexistent/directory"))

    def test_load_master_data_files_missing_model_class(self, tmp_path):
        """MODEL_CLASS が定義されていない"""
        master_file = tmp_path / "001_test.py"
        master_file.write_text(
            """
MASTER_DATA = [{"id": 1}]
"""
        )

        with pytest.raises(ValueError, match="MODEL_CLASS が定義されていません"):
            list(load_master_data_files(str(tmp_path)))

    def test_load_master_data_files_missing_master_data(self, tmp_path):
        """MASTER_DATA が定義されていない"""
        master_file = tmp_path / "001_test.py"
        master_file.write_text(
            """
from repom.models.sample import SampleModel

MODEL_CLASS = SampleModel
"""
        )

        with pytest.raises(ValueError, match="MASTER_DATA が定義されていません"):
            list(load_master_data_files(str(tmp_path)))

    def test_load_master_data_files_invalid_data_type(self, tmp_path):
        """MASTER_DATA が list 型でない"""
        master_file = tmp_path / "001_test.py"
        master_file.write_text(
            """
from repom.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = {"id": 1}  # dict型（エラー）
"""
        )

        with pytest.raises(ValueError, match="MASTER_DATA は list 型である必要があります"):
            list(load_master_data_files(str(tmp_path)))

    def test_load_master_data_files_ignores_private_files(self, tmp_path):
        """アンダースコアで始まるファイルは無視"""
        # 通常のファイル
        file1 = tmp_path / "001_test.py"
        file1.write_text(
            """
from repom.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = [{"id": 1}]
"""
        )

        # プライベートファイル（無視されるべき）
        file2 = tmp_path / "_private.py"
        file2.write_text(
            """
from repom.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = [{"id": 999}]
"""
        )

        results = list(load_master_data_files(str(tmp_path)))
        assert len(results) == 1  # _private.py は無視される


class TestSyncMasterData:
    """マスターデータ同期のテスト"""

    def test_sync_master_data_insert(self, db_test):
        """新規データの INSERT"""
        data_list = [
            {"id": 100, "value": "new record 1", "done_at": None},
            {"id": 101, "value": "new record 2", "done_at": None},
        ]

        count = sync_master_data(SampleModel, data_list, db_test)

        assert count == 2

        # データが挿入されたか確認
        repo = BaseRepository(SampleModel, db_test)
        record1 = repo.get_by_id(100)
        record2 = repo.get_by_id(101)

        assert record1 is not None
        assert record1.value == "new record 1"
        assert record2 is not None
        assert record2.value == "new record 2"

    def test_sync_master_data_update(self, db_test):
        """既存データの UPDATE"""
        # 初期データを挿入
        repo = BaseRepository(SampleModel, db_test)
        initial = SampleModel(id=200, value="initial value", done_at=None)
        repo.save(initial)
        db_test.commit()

        # 同じ id で異なる値を同期
        data_list = [
            {"id": 200, "value": "updated value", "done_at": None},
        ]

        count = sync_master_data(SampleModel, data_list, db_test)

        assert count == 1

        # データが更新されたか確認
        db_test.expire_all()  # キャッシュをクリア
        updated = repo.get_by_id(200)
        assert updated is not None
        assert updated.value == "updated value"

    def test_sync_master_data_mixed_insert_and_update(self, db_test):
        """INSERT と UPDATE の混在"""
        # 既存データ
        repo = BaseRepository(SampleModel, db_test)
        existing = SampleModel(id=300, value="existing", done_at=None)
        repo.save(existing)
        db_test.commit()

        # 既存 (300) + 新規 (301, 302)
        data_list = [
            {"id": 300, "value": "updated existing", "done_at": None},
            {"id": 301, "value": "new record 1", "done_at": None},
            {"id": 302, "value": "new record 2", "done_at": None},
        ]

        count = sync_master_data(SampleModel, data_list, db_test)

        assert count == 3

        # 確認
        db_test.expire_all()
        record300 = repo.get_by_id(300)
        record301 = repo.get_by_id(301)
        record302 = repo.get_by_id(302)

        assert record300.value == "updated existing"
        assert record301.value == "new record 1"
        assert record302.value == "new record 2"

    def test_sync_master_data_empty_list(self, db_test):
        """空のリスト"""
        count = sync_master_data(SampleModel, [], db_test)
        assert count == 0

    def test_sync_master_data_transaction_rollback(self, db_test):
        """トランザクションロールバック（エラー時）"""
        repo = BaseRepository(SampleModel, db_test)

        # 不正なデータ（例: 存在しないカラム）
        data_list = [
            {"id": 400, "value": "valid"},
            {"id": 401, "value": "test", "nonexistent_column": "error"},  # 存在しないカラム → エラー
        ]

        with pytest.raises(Exception):
            sync_master_data(SampleModel, data_list, db_test)

        # ロールバックされて、400 も挿入されていないはず
        # （ただし db_test フィクスチャ自体が各テストでロールバックする）
        record400 = repo.get_by_id(400)
        assert record400 is None
