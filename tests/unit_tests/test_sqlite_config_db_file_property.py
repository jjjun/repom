"""Test SQLiteConfig db_file property auto-calculation.

This test validates Option 1 implementation: db_file as a property that
automatically recalculates based on db_name without explicit reset.
"""
import pytest
from repom.config import RepomConfig


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

    def test_db_file_path_property_works_with_auto_calculation(self):
        """db_file_path プロパティが自動計算と連携する"""
        config = RepomConfig()
        config.db_name = 'myapp'
        config.exec_env = 'dev'

        # db_file_path は db_file の自動計算を使用する
        # db_path が設定されている場合のみ有効
        if config.sqlite.db_file_path:
            assert 'myapp_dev.sqlite3' in config.sqlite.db_file_path
