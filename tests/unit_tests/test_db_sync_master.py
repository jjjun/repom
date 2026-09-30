"""
db_sync_master のテスト

マスターデータ同期機能のテスト：
- ファイル読み込み
- Upsert ロジック（INSERT / UPDATE）
- トランザクションロールバック
- エラーハンドリング
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event
from repom.scripts import db_sync_master as db_sync_master_script
from repom.scripts.db_sync_master import load_master_data_files, sync_master_data
from repom.examples.models.sample import SampleModel
from repom.repositories import BaseRepository


class TestLoadMasterDataFiles:
    """マスターデータファイル読み込みのテスト"""

    def test_load_master_data_files_success(self, tmp_path):
        """正常なマスターデータファイルの読み込み"""
        # テスト用のマスターデータファイルを作成
        master_file = tmp_path / "001_test.py"
        master_file.write_text(
            """
from repom.examples.models.sample import SampleModel

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
from repom.examples.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = [{"id": 2, "value": "second"}]
"""
        )

        file1 = tmp_path / "001_first.py"
        file1.write_text(
            """
from repom.examples.models.sample import SampleModel

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
from repom.examples.models.sample import SampleModel

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
from repom.examples.models.sample import SampleModel

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
from repom.examples.models.sample import SampleModel

MODEL_CLASS = SampleModel
MASTER_DATA = [{"id": 1}]
"""
        )

        # プライベートファイル（無視されるべき）
        file2 = tmp_path / "_private.py"
        file2.write_text(
            """
from repom.examples.models.sample import SampleModel

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

    def test_sync_master_data_unchanged_data_keeps_updated_at(self, db_test):
        """同一データを2回同期しても UPDATE が発行されず updated_at が変わらないこと"""
        repo = BaseRepository(SampleModel, db_test)
        data_list = [{"id": 500, "value": "same value", "done_at": None}]

        sync_master_data(SampleModel, data_list, db_test)
        db_test.commit()
        first_updated_at = repo.get_by_id(500).updated_at

        statements = []

        def capture_statement(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(db_test.bind, 'before_cursor_execute', capture_statement)
        try:
            sync_master_data(SampleModel, data_list, db_test)
            db_test.commit()
        finally:
            event.remove(db_test.bind, 'before_cursor_execute', capture_statement)

        assert not any(
            statement.lstrip().upper().startswith('UPDATE') for statement in statements
        )

        db_test.expire_all()
        assert repo.get_by_id(500).updated_at == first_updated_at

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


def test_main_exits_when_master_data_path_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(
        db_sync_master_script,
        "config",
        SimpleNamespace(master_data_path=None, db_type="sqlite"),
    )
    monkeypatch.setattr(db_sync_master_script, "load_models", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        db_sync_master_script.main()

    assert exc_info.value.code == 1
    assert "master_data_path が設定されていません" in capsys.readouterr().out


def test_main_starts_postgres_and_reports_empty_directory(monkeypatch, tmp_path, capsys):
    events = []
    monkeypatch.setattr(
        db_sync_master_script,
        "config",
        SimpleNamespace(
            master_data_path=str(tmp_path), db_type="postgres", db_url_overridden=False
        ),
    )
    monkeypatch.setattr(db_sync_master_script, "load_models", lambda: None)

    from repom.postgres import manage as postgres_manage

    monkeypatch.setattr(postgres_manage, "ensure_running", lambda: events.append("postgres"))

    @contextmanager
    def transaction():
        events.append("transaction")
        yield object()

    monkeypatch.setattr(db_sync_master_script, "get_standalone_sync_transaction", transaction)

    db_sync_master_script.main()

    output = capsys.readouterr().out
    assert events == ["postgres", "transaction"]
    assert "マスターデータファイルが見つかりません" in output
    assert "同期完了: 0 ファイル、0 レコード" in output


def test_main_skips_managed_postgres_for_url_override(monkeypatch, tmp_path):
    monkeypatch.setattr(
        db_sync_master_script,
        "config",
        SimpleNamespace(
            master_data_path=str(tmp_path), db_type="postgres", db_url_overridden=True
        ),
    )
    monkeypatch.setattr(db_sync_master_script, "load_models", lambda: None)

    from repom.postgres import manage as postgres_manage

    ensure_running = MagicMock(side_effect=AssertionError("managed container must not start"))
    monkeypatch.setattr(postgres_manage, "ensure_running", ensure_running)

    @contextmanager
    def transaction():
        yield object()

    monkeypatch.setattr(db_sync_master_script, "get_standalone_sync_transaction", transaction)
    monkeypatch.setattr(db_sync_master_script, "load_master_data_files", lambda _directory: iter([]))

    db_sync_master_script.main()

    ensure_running.assert_not_called()


@pytest.mark.parametrize(
    ("error_type", "message"),
    [
        (FileNotFoundError, "missing directory"),
        (ValueError, "invalid master data"),
        (RuntimeError, "unexpected failure"),
    ],
)
def test_main_reports_master_data_errors_and_exits(
    monkeypatch, tmp_path, capsys, error_type, message
):
    monkeypatch.setattr(
        db_sync_master_script,
        "config",
        SimpleNamespace(master_data_path=str(tmp_path), db_type="sqlite"),
    )
    monkeypatch.setattr(db_sync_master_script, "load_models", lambda: None)

    @contextmanager
    def transaction():
        yield object()

    monkeypatch.setattr(db_sync_master_script, "get_standalone_sync_transaction", transaction)

    def load_files(_directory):
        raise error_type(message)
        yield

    monkeypatch.setattr(db_sync_master_script, "load_master_data_files", load_files)

    with pytest.raises(SystemExit) as exc_info:
        db_sync_master_script.main()

    output = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert message in output


def test_main_reports_successful_sync_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        db_sync_master_script,
        "config",
        SimpleNamespace(master_data_path=str(tmp_path), db_type="sqlite"),
    )
    monkeypatch.setattr(db_sync_master_script, "load_models", lambda: None)

    @contextmanager
    def transaction():
        yield object()

    monkeypatch.setattr(db_sync_master_script, "get_standalone_sync_transaction", transaction)
    monkeypatch.setattr(
        db_sync_master_script,
        "load_master_data_files",
        lambda _directory: iter([(SampleModel, [{"id": 1}])]),
    )
    monkeypatch.setattr(db_sync_master_script, "sync_master_data", lambda *_args: 1)

    db_sync_master_script.main()

    output = capsys.readouterr().out
    assert "SampleModel: 1 件" in output
    assert "同期完了: 1 ファイル、1 レコード" in output
