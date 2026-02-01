"""
PostgreSQL config support tests

このテストファイルは RepomConfig のプロパティのみをテストし、
実際のデータベース接続は行いません。

config.db_type をデフォルトの 'sqlite' のままにして実行します。
"""
import pytest
import os


class TestPostgresDBType:
    """DB type property tests"""

    def test_db_type_default(self):
        """デフォルトは sqlite"""
        from repom.config import RepomConfig
        config = RepomConfig()
        # 環境変数未設定時
        os.environ.pop('DB_TYPE', None)
        assert config.db_type == 'sqlite'

    def test_db_type_setter_postgres(self):
        """Setter で postgres に設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        assert config.db_type == 'postgres'

    def test_db_type_setter_sqlite(self):
        """Setter で sqlite に設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        assert config.db_type == 'sqlite'

    def test_db_type_invalid(self):
        """無効な値でエラー"""
        from repom.config import RepomConfig
        config = RepomConfig()

        with pytest.raises(ValueError, match="Invalid DB_TYPE"):
            config.db_type = 'mysql'

        with pytest.raises(ValueError, match="Invalid DB_TYPE"):
            config.db_type = 'oracle'


class TestPostgresProperties:
    """PostgreSQL connection properties tests"""

    def test_postgres_host_default(self):
        """デフォルトは localhost"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('POSTGRES_HOST', None)
        assert config.postgres_host == 'localhost'

    def test_postgres_host_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres_host = 'my-server'
        assert config.postgres_host == 'my-server'

    def test_postgres_port_default(self):
        """デフォルトは 5432"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('POSTGRES_PORT', None)
        assert config.postgres_port == 5432

    def test_postgres_port_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres_port = 5433
        assert config.postgres_port == 5433

    def test_postgres_user_default(self):
        """デフォルトは repom"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('POSTGRES_USER', None)
        assert config.postgres_user == 'repom'

    def test_postgres_user_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres_user = 'myuser'
        assert config.postgres_user == 'myuser'

    def test_postgres_password_default(self):
        """デフォルトは repom_dev"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('POSTGRES_PASSWORD', None)
        assert config.postgres_password == 'repom_dev'

    def test_postgres_password_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres_password = 'mypass'
        assert config.postgres_password == 'mypass'


class TestPostgresDBName:
    """PostgreSQL database name generation tests"""

    def test_postgres_db_setter(self):
        """Setter で直接設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres_db = 'custom_db'
        assert config.postgres_db == 'custom_db'

    def test_postgres_db_property_returns_set_value(self):
        """設定値が優先される"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config._postgres_db = 'my_custom_db'
        # exec_env に関係なく設定値が返される
        assert config.postgres_db == 'my_custom_db'


class TestPostgresURL:
    """PostgreSQL URL generation tests"""

    def test_db_url_postgres_basic(self):
        """PostgreSQL の基本的な URL 生成"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        config.root_path = '/tmp/repom'

        # デフォルト値を使用
        url = config.db_url
        assert url.startswith('postgresql+psycopg://')
        assert 'repom:repom_dev@localhost:5432/' in url

    def test_db_url_postgres_custom(self):
        """PostgreSQL のカスタム設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        config.postgres_host = 'my-server'
        config.postgres_port = 5433
        config.postgres_user = 'myuser'
        config.postgres_password = 'mypass'
        config.postgres_db = 'mydb'

        expected = 'postgresql+psycopg://myuser:mypass@my-server:5433/mydb'
        assert config.db_url == expected

    def test_db_url_sqlite_unchanged(self):
        """SQLite URL は変更なし（後方互換性）"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        config.root_path = '/tmp/repom'
        config.init()

        # SQLite URL
        assert config.db_url.startswith('sqlite:///')


class TestEngineKwargs:
    """Engine kwargs tests for different database types"""

    def test_engine_kwargs_postgres(self):
        """PostgreSQL の engine_kwargs"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'

        kwargs = config.engine_kwargs

        # PostgreSQL 用の完全なプール設定
        assert kwargs['pool_size'] == 10
        assert kwargs['max_overflow'] == 20
        assert kwargs['pool_timeout'] == 30
        assert kwargs['pool_recycle'] == 3600
        assert kwargs['pool_pre_ping'] is True

        # SQLite 固有の設定は含まれない
        assert 'connect_args' not in kwargs
        assert 'poolclass' not in kwargs

    def test_engine_kwargs_sqlite_file(self):
        """SQLite ファイルベースの engine_kwargs（後方互換性）"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        config.root_path = '/tmp/repom'
        config.use_in_memory_db_for_tests = False
        config.init()

        kwargs = config.engine_kwargs

        # QueuePool 用の設定
        assert kwargs['pool_size'] == 10
        assert kwargs['max_overflow'] == 20
        assert kwargs['pool_timeout'] == 30
        assert kwargs['pool_recycle'] == 3600
        assert kwargs['pool_pre_ping'] is True

        # SQLite 用の connect_args
        assert 'connect_args' in kwargs
        assert kwargs['connect_args']['check_same_thread'] is False

    def test_engine_kwargs_sqlite_memory(self):
        """SQLite :memory: の engine_kwargs（後方互換性）"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        config.root_path = '/tmp/repom'
        config._db_url = 'sqlite:///:memory:'

        kwargs = config.engine_kwargs

        # StaticPool が使われる
        assert 'poolclass' in kwargs
        assert kwargs['poolclass'].__name__ == 'StaticPool'
        assert 'connect_args' in kwargs
        assert kwargs['connect_args']['check_same_thread'] is False

        # pool_size などは含まれない（StaticPool は未サポート）
        assert 'pool_size' not in kwargs
        assert 'max_overflow' not in kwargs


class TestBackwardCompatibility:
    """Backward compatibility tests - 既存の SQLite 機能が壊れていないか"""

    def test_default_is_sqlite(self):
        """デフォルトは SQLite のまま"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('DB_TYPE', None)
        assert config.db_type == 'sqlite'

    def test_sqlite_db_url_unchanged(self):
        """SQLite の db_url 生成は変更なし"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.root_path = '/tmp/repom'
        config.init()

        # デフォルトは SQLite
        assert config.db_type == 'sqlite'
        assert config.db_url.startswith('sqlite:///')

    def test_in_memory_db_for_tests_works(self):
        """テスト用の in-memory DB は引き続き動作"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.root_path = '/tmp/repom'
        config._exec_env = 'test'
        config.use_in_memory_db_for_tests = True

        assert config.db_url == 'sqlite:///:memory:'


class TestURLOverride:
    """db_url の直接設定が優先されることを確認"""

    def test_db_url_setter_overrides_postgres(self):
        """_db_url が設定されていれば、PostgreSQL 設定より優先"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        config._db_url = 'postgresql://custom:url@example.com/db'

        assert config.db_url == 'postgresql://custom:url@example.com/db'

    def test_db_url_setter_overrides_sqlite(self):
        """_db_url が設定されていれば、SQLite 設定より優先"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        config._db_url = 'sqlite:///custom/path/db.sqlite3'

        assert config.db_url == 'sqlite:///custom/path/db.sqlite3'
