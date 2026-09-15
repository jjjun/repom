"""
PostgreSQL config support tests

このテストファイルは RepomConfig のプロパティのみをテストし、
実際のデータベース接続は行いません。

config.db_type をデフォルトの 'sqlite' のままにして実行します。
"""
import pytest
import os

from sqlalchemy.engine.url import make_url


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
        assert config.postgres.host == 'localhost'

    def test_postgres_host_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.host = 'my-server'
        assert config.postgres.host == 'my-server'

    def test_postgres_port_default(self):
        """デフォルトは 5432"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('POSTGRES_PORT', None)
        assert config.postgres.port == 5432

    def test_postgres_port_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.port = 5433
        assert config.postgres.port == 5433

    def test_postgres_user_default(self):
        """デフォルトは repom"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('POSTGRES_USER', None)
        assert config.postgres.user == 'repom'

    def test_postgres_user_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.user = 'myuser'
        assert config.postgres.user == 'myuser'

    def test_postgres_password_default(self):
        """デフォルトは CHANGE_ME"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('POSTGRES_PASSWORD', None)
        assert config.postgres.password == 'CHANGE_ME'

    def test_postgres_password_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.password = 'mypass'
        assert config.postgres.password == 'mypass'


class TestPostgresDBName:
    """PostgreSQL database name generation tests"""

    def test_postgres_db_setter(self):
        """Setter で直接設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.database = 'custom_db'
        assert config.postgres_db == 'custom_db'

    def test_postgres_db_property_returns_set_value(self):
        """設定値が優先される"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.database = 'my_custom_db'
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
        assert 'repom:CHANGE_ME@localhost:5432/' in url

    def test_db_url_postgres_custom(self):
        """PostgreSQL のカスタム設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        config.postgres.host = 'my-server'
        config.postgres.port = 5433
        config.postgres.user = 'myuser'
        config.postgres.password = 'mypass'
        config.postgres.database = 'mydb'

        expected = 'postgresql+psycopg://myuser:mypass@my-server:5433/mydb?sslmode=prefer'
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

        # PostgreSQL 接続タイムアウトと application_name
        assert kwargs['connect_args']['connect_timeout'] == 10
        assert kwargs['connect_args']['application_name'] == config.package_name

        # SQLite 固有の設定は含まれない
        assert 'poolclass' not in kwargs

    def test_engine_kwargs_sqlite_file(self):
        """SQLite ファイルベースの engine_kwargs（後方互換性）"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        config.root_path = '/tmp/repom'
        config.sqlite.use_in_memory_for_tests = False
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
        config.sqlite.use_in_memory_for_tests = True

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


class TestPostgresURLEncoding:
    """db_url が特殊文字を含む値を正しくパーセントエンコードすることを確認"""

    @pytest.mark.parametrize(
        "password",
        ["p@ss", "p/ss", "p?ss", "p#ss", "p ss"],
    )
    def test_db_url_encodes_special_characters_in_password(self, password):
        """@ / ? # とスペースを含むパスワードが make_url で正しく復元される"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        config.postgres.password = password

        url = make_url(config.db_url)

        assert url.password == password

    @pytest.mark.parametrize(
        ("postgres_attr", "url_attr", "value"),
        [
            ("user", "username", "us@er"),
            ("database", "database", "db#name"),
        ],
    )
    def test_db_url_encodes_special_characters_in_user_and_database(
        self, postgres_attr, url_attr, value
    ):
        """user / database に含まれる特殊文字も make_url で正しく復元される"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        setattr(config.postgres, postgres_attr, value)

        url = make_url(config.db_url)

        assert getattr(url, url_attr) == value


class TestPostgresSSLMode:
    """postgres_sslmode の既定値と prod での検証を確認"""

    def test_db_url_sets_sslmode_from_config(self):
        """config.postgres.sslmode が db_url の sslmode クエリに反映される"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        config.postgres.sslmode = 'verify-full'

        url = make_url(config.db_url)

        assert url.query["sslmode"] == "verify-full"

    def test_postgres_sslmode_defaults_by_exec_env(self):
        """明示指定がない場合、prod はリモートホストで require、それ以外は prefer"""
        from repom.config import RepomConfig

        config_dev = RepomConfig(exec_env='dev')
        config_dev.db_type = 'postgres'
        assert config_dev.postgres_sslmode == 'prefer'

        config_prod = RepomConfig(exec_env='prod')
        config_prod.db_type = 'postgres'
        config_prod.postgres.host = 'db.example.com'
        assert config_prod.postgres_sslmode == 'require'

    @pytest.mark.parametrize("local_host", ["localhost", "127.0.0.1", "::1"])
    def test_prod_local_host_defaults_to_prefer(self, local_host):
        """prod + ローカルホスト + 明示指定なしは prefer を既定とし、
        repom-generated なコンテナ（SSL 未対応）への接続を壊さない"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_type = 'postgres'
        config.postgres.host = local_host

        assert config.postgres_sslmode == 'prefer'

        url = config.db_url

        assert "sslmode=prefer" in url

    def test_prod_remote_host_defaults_to_require(self):
        """prod + リモートホスト + 明示指定なしは require を既定とする"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_type = 'postgres'
        config.postgres.host = 'db.example.com'

        assert config.postgres_sslmode == 'require'
        assert "sslmode=require" in config.db_url

    def test_explicit_sslmode_overrides_prod_local_default(self):
        """prod + ローカルホストでも config.postgres.sslmode の明示値が優先される"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_type = 'postgres'
        config.postgres.host = 'localhost'
        config.postgres.sslmode = 'verify-full'

        assert config.postgres_sslmode == 'verify-full'
        assert "sslmode=verify-full" in config.db_url

    def test_prod_requires_ssl_for_remote_host(self):
        """exec_env=prod + リモートホスト + 弱い sslmode は db_url で拒否される"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_type = 'postgres'
        config.postgres.host = 'db.example.com'
        config.postgres.sslmode = 'prefer'

        with pytest.raises(ValueError, match="sslmode"):
            config.db_url

    @pytest.mark.parametrize("local_host", ["localhost", "127.0.0.1", "::1"])
    def test_prod_allows_localhost_without_ssl(self, local_host):
        """ローカル Docker ワークフローは prod でも sslmode 検証の対象外"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_type = 'postgres'
        config.postgres.host = local_host
        config.postgres.sslmode = 'prefer'

        url = config.db_url

        assert "sslmode=prefer" in url
