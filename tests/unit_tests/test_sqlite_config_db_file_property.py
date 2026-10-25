"""Test SQLiteConfig db_file property auto-calculation.

This test validates Option 1 implementation: db_file as a property that
automatically recalculates based on db_name without explicit reset.
"""
import pytest

from repom.config import RepomConfig
from repom.sqlite.config import SqliteConfig, validate_sqlite_db_file_name

UNSAFE_DB_FILE_NAMES = [
    "../x",
    "..",
    "a/b",
    "a\\b",
    "x?mode=rw&uri=true",
    "x#y",
    "C:",
    "C:x",
    "file:x",
    "a\x00b",
    "a\x1fb",
    "a\x7fb",
    "a\x85b",
]


class TestSqliteConfigDbFileProperty:
    """Test that db_file property automatically recalculates when db_name changes."""

    def test_db_file_auto_calculated_from_db_name(self):
        """db_file は db_name に基づいて自動計算される"""
        config = RepomConfig()
        config.db_name = 'myapp'
        config.exec_env = 'dev'

        # db_file は自動計算される（明示的な初期化は不要）
        assert config.sqlite.db_file == 'myapp_dev.sqlite3'

    def test_db_file_changes_when_db_name_changes(self):
        """db_name を変更すると db_file も自動的に再計算される"""
        config = RepomConfig()
        config.db_name = 'app1'
        config.exec_env = 'dev'

        # 最初の状態
        assert config.sqlite.db_file == 'app1_dev.sqlite3'

        # db_name を変更
        config.db_name = 'app2'

        # db_file は自動的に再計算される（リセットの必要なし）
        assert config.sqlite.db_file == 'app2_dev.sqlite3'

    def test_db_file_explicit_setting_takes_priority(self):
        """明示的に db_file を設定した場合はそれを使用"""
        config = RepomConfig()
        config.db_name = 'myapp'
        config.exec_env = 'dev'

        # 明示的に設定
        config.sqlite.db_file = 'custom.db'

        # 明示的な設定が優先される
        assert config.sqlite.db_file == 'custom.db'

        # db_name を変更しても明示的な設定は変わらない
        config.db_name = 'otherapp'
        assert config.sqlite.db_file == 'custom.db'

    def test_db_file_reset_to_default_by_setting_to_none(self):
        """db_file を None に設定すると、db_name から自動計算に戻る"""
        config = RepomConfig()
        config.db_name = 'myapp'
        config.exec_env = 'dev'

        # 最初は自動計算
        assert config.sqlite.db_file == 'myapp_dev.sqlite3'

        # 明示的に設定
        config.sqlite.db_file = 'custom.db'
        assert config.sqlite.db_file == 'custom.db'

        # None に設定して自動計算に戻す
        config.sqlite.db_file = None

        # db_name から自動計算される
        assert config.sqlite.db_file == 'myapp_dev.sqlite3'

    def test_db_file_different_environments(self):
        """環境別に正しい db_file が生成される"""
        config = RepomConfig()
        config.db_name = 'testapp'

        # dev environment
        config.exec_env = 'dev'
        assert config.sqlite.db_file == 'testapp_dev.sqlite3'

        # test environment
        config.exec_env = 'test'
        assert config.sqlite.db_file == 'testapp_test.sqlite3'

        # prod environment
        config.exec_env = 'prod'
        assert config.sqlite.db_file == 'testapp.sqlite3'

    def test_external_project_workflow(self):
        """外部プロジェクトでの使用フロー（回避策が不要になる）"""
        # 外部プロジェクトでの CONFIG_HOOK での設定
        config = RepomConfig()
        config.db_name = 'mine_py'
        config.exec_env = 'dev'

        # 以前は config.sqlite.db_file = None をリセットする必要があった
        # 今は不要！property が自動計算する
        db_file = config.sqlite.db_file

        assert db_file == 'mine_py_dev.sqlite3'

        # db_url でも正しく使用される
        assert 'mine_py_dev.sqlite3' in config.db_url

    def test_db_file_path_property_works_with_auto_calculation(self, tmp_path):
        """db_file_path プロパティが自動計算と連携する"""
        config = RepomConfig()
        config.db_name = 'myapp'
        config.exec_env = 'dev'
        config.sqlite.db_path = str(tmp_path)

        # db_file_path は db_file の自動計算を使用する
        assert 'myapp_dev.sqlite3' in config.sqlite.db_file_path


@pytest.mark.parametrize("value", UNSAFE_DB_FILE_NAMES)
def test_db_file_setter_rejects_unsafe_names(value):
    config = RepomConfig()
    config.sqlite.db_file = "custom.db"

    with pytest.raises(ValueError, match="sqlite.db_file must be a plain file name"):
        config.sqlite.db_file = value

    assert config.sqlite.db_file == "custom.db"


@pytest.mark.parametrize("value", UNSAFE_DB_FILE_NAMES)
def test_default_db_file_rejects_unsafe_db_name(value):
    config = RepomConfig()
    config.exec_env = "dev"
    config.db_name = value

    with pytest.raises(ValueError, match="db_name must be a plain file name"):
        config.sqlite.db_file

    with pytest.raises(ValueError, match="db_name must be a plain file name"):
        config.sqlite.get_default_db_file("prod")


@pytest.mark.parametrize(
    "value", ["custom.sqlite3", "my app.db", "データ.sqlite3", "a-b_c.1.db", "100%.db"]
)
def test_db_file_accepts_plain_names_with_spaces_and_unicode(value):
    config = RepomConfig()
    config.sqlite.db_file = value

    assert config.sqlite.db_file == value


def test_empty_db_file_still_selects_no_file():
    config = RepomConfig()
    config.exec_env = "dev"
    config.sqlite.use_in_memory_for_tests = False

    config.sqlite.db_file = ""

    assert config.sqlite.db_file_path is None
    assert config.db_url is None


def test_validate_sqlite_db_file_name_rejects_empty_and_returns_valid_names():
    assert validate_sqlite_db_file_name("a.sqlite3", field_name="x") == "a.sqlite3"

    with pytest.raises(ValueError, match="x must be a plain file name"):
        validate_sqlite_db_file_name("", field_name="x")


def test_unbound_sqlite_config_has_no_derived_paths():
    config = SqliteConfig()

    assert config.db_file is None
    assert config.db_file_path is None
