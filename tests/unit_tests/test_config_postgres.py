"""
PostgreSQL config support tests

このテストファイルは RepomConfig のプロパティのみをテストし、
実際のデータベース接続は行いません。

config.db_type をデフォルトの 'sqlite' のままにして実行します。
"""
import pytest

from sqlalchemy.engine.url import make_url


class TestPostgresDBType:
    """DB type property tests"""

    def test_db_type_default(self, monkeypatch):
        """デフォルトは sqlite"""
        from repom.config import RepomConfig
        config = RepomConfig()
        # 環境変数未設定時
        monkeypatch.delenv('DB_TYPE', raising=False)
        assert config.db_type == 'sqlite'

    def test_db_type_follows_overridden_url_backend(self):
        from repom.config import RepomConfig

        config = RepomConfig()
        config.db_url = "postgresql://app:secret@db.example.internal/appdb"

        assert config.db_url_overridden is True
        assert config.db_type == "postgres"

        config.db_url = "sqlite:///app.sqlite3"
        assert config.db_type == "sqlite"

    def test_conflicting_db_type_warns_once_and_url_wins(self, caplog):
        from repom.config import RepomConfig

        config = RepomConfig()
        config.db_type = "postgres"
        config.db_url = "sqlite:///app.sqlite3"

        with caplog.at_level("WARNING"):
            assert config.db_type == "sqlite"
            assert config.db_type == "sqlite"

        assert caplog.text.count("disagrees with the database URL backend") == 1

    def test_db_type_without_url_override_keeps_configured_value(self):
        from repom.config import RepomConfig

        config = RepomConfig()
        config.db_type = "postgres"

        assert config.db_url_overridden is False
        assert config.db_type == "postgres"

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

    def test_postgres_host_default(self, monkeypatch):
        """デフォルトは 127.0.0.1"""
        from repom.config import RepomConfig
        config = RepomConfig()
        monkeypatch.delenv('POSTGRES_HOST', raising=False)
        assert config.postgres.host == '127.0.0.1'

    def test_postgres_host_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.host = 'my-server'
        assert config.postgres.host == 'my-server'

    def test_postgres_port_default(self, monkeypatch):
        """デフォルトは 5432"""
        from repom.config import RepomConfig
        config = RepomConfig()
        monkeypatch.delenv('POSTGRES_PORT', raising=False)
        assert config.postgres.port == 5432

    def test_postgres_port_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.port = 5433
        assert config.postgres.port == 5433

    def test_postgres_user_default(self, monkeypatch):
        """デフォルトは repom"""
        from repom.config import RepomConfig
        config = RepomConfig()
        monkeypatch.delenv('POSTGRES_USER', raising=False)
        assert config.postgres.user == 'repom'

    def test_postgres_user_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.postgres.user = 'myuser'
        assert config.postgres.user == 'myuser'

    def test_postgres_password_default(self, monkeypatch):
        """デフォルトは CHANGE_ME"""
        from repom.config import RepomConfig
        config = RepomConfig()
        monkeypatch.delenv('POSTGRES_PASSWORD', raising=False)
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

class TestPostgresURL:
    """PostgreSQL URL generation tests"""

    def test_db_url_postgres_basic(self, tmp_path):
        """PostgreSQL の基本的な URL 生成"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'postgres'
        config.root_path = str(tmp_path)

        # デフォルト値を使用
        url = config.db_url
        assert url.startswith('postgresql+psycopg://')
        assert 'repom:CHANGE_ME@127.0.0.1:5432/' in url

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

    def test_db_url_sqlite_unchanged(self, tmp_path):
        """SQLite URL は変更なし（後方互換性）"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        config.root_path = str(tmp_path)
        config.init()

        # SQLite URL
        assert config.db_url.startswith('sqlite:///')


class TestBackwardCompatibility:
    """Backward compatibility tests - 既存の SQLite 機能が壊れていないか"""

    def test_in_memory_db_for_tests_works(self, tmp_path):
        """テスト用の in-memory DB は引き続き動作"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.root_path = str(tmp_path)
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

        assert config.db_url == 'postgresql://custom:url@example.com/db?sslmode=prefer'

    def test_db_url_setter_overrides_sqlite(self):
        """_db_url が設定されていれば、SQLite 設定より優先"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.db_type = 'sqlite'
        config._db_url = 'sqlite:///custom/path/db.sqlite3'

        assert config.db_url == 'sqlite:///custom/path/db.sqlite3'

    def test_prod_remote_postgres_override_adds_required_sslmode(self):
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_url = (
            'postgresql+psycopg://app:secret@db.example.internal:5432/appdb'
            '?application_name=worker&connect_timeout=8'
        )

        url = make_url(config.db_url)

        assert url.password == 'secret'
        assert url.query == {
            'application_name': 'worker',
            'connect_timeout': '8',
            'sslmode': 'require',
        }

    @pytest.mark.parametrize('sslmode', ['disable', 'prefer'])
    def test_prod_remote_postgres_override_rejects_weak_sslmode(self, sslmode):
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_url = (
            'postgresql://app:secret@db.example.internal/appdb'
            f'?sslmode={sslmode}'
        )

        with pytest.raises(ValueError, match="db.example.internal.*URL query"):
            config.db_url

    @pytest.mark.parametrize(
        ('exec_env', 'host', 'expected_sslmode'),
        [
            ('prod', 'localhost', 'prefer'),
            ('prod', None, 'prefer'),
            ('dev', 'db.example.internal', 'prefer'),
            ('test', 'db.example.internal', 'prefer'),
        ],
    )
    def test_postgres_override_defaults_by_environment_and_host(
        self, exec_env, host, expected_sslmode
    ):
        from repom.config import RepomConfig
        if host is None:
            override = 'postgresql+psycopg:///appdb'
        else:
            override = f'postgresql+psycopg://{host}/appdb'
        config = RepomConfig(exec_env=exec_env)
        config.db_url = override

        url = make_url(config.db_url)

        assert url.host == host
        assert url.query['sslmode'] == expected_sslmode

    def test_postgres_override_respects_url_tls_and_config_defaults(self):
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.postgres.sslmode = 'verify-full'
        config.postgres.sslrootcert = '/etc/ssl/certs/default-ca.pem'
        config.db_url = (
            'postgresql://app:secret@db.example.internal/appdb'
            '?sslmode=verify-full&sslrootcert=/etc/ssl/certs/url-ca.pem'
        )

        explicit_url = make_url(config.db_url)

        assert explicit_url.query['sslmode'] == 'verify-full'
        assert explicit_url.query['sslrootcert'] == '/etc/ssl/certs/url-ca.pem'

        config.db_url = 'postgresql://app:secret@db.example.internal/appdb'
        configured_url = make_url(config.db_url)

        assert configured_url.query['sslmode'] == 'verify-full'
        assert configured_url.query['sslrootcert'] == '/etc/ssl/certs/default-ca.pem'

    def test_postgres_override_keeps_configured_sslrootcert_with_existing_mode_absent_cert(self):
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.postgres.sslrootcert = '/etc/ssl/certs/default-ca.pem'
        config.db_url = (
            'postgresql://app:secret@db.example.internal/appdb?sslmode=verify-full'
        )

        url = make_url(config.db_url)

        assert url.query['sslmode'] == 'verify-full'
        assert 'sslrootcert' not in url.query

    def test_sqlite_override_is_returned_unchanged(self):
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        override = 'sqlite:///custom/path/db.sqlite3?mode=ro'
        config.db_url = override

        assert config.db_url == override


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

    @pytest.mark.parametrize("exec_env", ["prod", "production", " Production "])
    def test_prod_requires_ssl_for_remote_host(self, exec_env):
        """exec_env=prod + リモートホスト + 弱い sslmode は db_url で拒否される"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env=exec_env)
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

    @pytest.mark.parametrize(
        "override",
        [
            "postgresql+psycopg://localhost/app?host=db.example.invalid&sslmode=disable",
            "postgresql+psycopg:///app?host=db.example.invalid&sslmode=prefer",
            "postgresql+psycopg://localhost/app?host=localhost,db.example.invalid&sslmode=allow",
            "postgresql+psycopg://localhost/app?hostaddr=198.51.100.5&sslmode=prefer",
            "postgresql+psycopg://localhost/app?host=localhost:5432&host=db.example.invalid:5432&sslmode=prefer",
            "postgresql+psycopg://localhost/app?host=localhost,db.example.invalid&hostaddr=127.0.0.1&sslmode=prefer",
        ],
    )
    def test_prod_rejects_weak_tls_for_effective_remote_destination(self, override):
        from repom.config import RepomConfig

        config = RepomConfig(exec_env="prod")
        config.db_url = override

        with pytest.raises(ValueError, match="sslmode"):
            config.db_url

    @pytest.mark.parametrize(
        "override",
        [
            "postgresql+psycopg://localhost/app?host=db.example.invalid",
            "postgresql+psycopg:///app?host=db.example.invalid",
            "postgresql+psycopg://localhost/app?host=localhost,db.example.invalid",
            "postgresql+psycopg://localhost/app?hostaddr=198.51.100.5",
            "postgresql+psycopg://localhost/app?host=localhost:5432&host=db.example.invalid:5432",
        ],
    )
    def test_prod_defaults_to_require_for_effective_remote_destination(self, override):
        from repom.config import RepomConfig

        config = RepomConfig(exec_env="prod")
        config.db_url = override

        assert make_url(config.db_url).query["sslmode"] == "require"

    @pytest.mark.parametrize(
        "override",
        [
            "postgresql+psycopg:///app?host=/var/run/postgresql&sslmode=prefer",
            "postgresql+psycopg:///app?host=localhost:5432&sslmode=prefer",
            "postgresql+psycopg://localhost/app?hostaddr=127.0.0.1&sslmode=prefer",
            "postgresql+psycopg:///app?hostaddr=127.0.0.1,127.0.0.2&sslmode=prefer",
            "postgresql+psycopg://[::1]/app?sslmode=prefer",
        ],
    )
    def test_prod_keeps_local_socket_and_loopback_tls_exceptions(self, override):
        from repom.config import RepomConfig

        config = RepomConfig(exec_env="prod")
        config.db_url = override

        assert make_url(config.db_url).query["sslmode"] == "prefer"


class TestPostgresTlsSettings:
    """postgres_tls_settings() は db_url とホストクライアントツールで共有される"""

    def test_local_default_is_prefer(self):
        """明示指定なし + ローカルホストは prefer で、sslrootcert は None"""
        from repom.config import PostgresTlsSettings, RepomConfig
        config = RepomConfig(exec_env='dev')
        config.postgres.host = 'localhost'

        tls = config.postgres_tls_settings()

        assert tls == PostgresTlsSettings(sslmode='prefer', sslrootcert=None)

    @pytest.mark.parametrize("exec_env", ["prod", "production", " Production "])
    def test_remote_prod_default_is_require(self, exec_env):
        """明示指定なし + prod + リモートホストは require"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env=exec_env)
        config.postgres.host = 'db.example.com'

        tls = config.postgres_tls_settings()

        assert tls.sslmode == 'require'
        assert tls.sslrootcert is None

    def test_explicit_verify_full_and_sslrootcert(self):
        """明示指定した sslmode / sslrootcert がそのまま反映される"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.postgres.host = 'db.example.com'
        config.postgres.sslmode = 'verify-full'
        config.postgres.sslrootcert = '/etc/ssl/certs/test-ca.pem'

        tls = config.postgres_tls_settings()

        assert tls.sslmode == 'verify-full'
        assert tls.sslrootcert == '/etc/ssl/certs/test-ca.pem'

    @pytest.mark.parametrize("exec_env", ["prod", "production", " Production "])
    def test_remote_prod_weak_sslmode_raises(self, exec_env):
        """prod + リモートホスト + 弱い sslmode は ValueError を送出する"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env=exec_env)
        config.postgres.host = 'db.example.com'
        config.postgres.sslmode = 'prefer'

        with pytest.raises(ValueError, match="sslmode"):
            config.postgres_tls_settings()

    def test_matches_db_url_sslmode(self):
        """db_url が使う sslmode と postgres_tls_settings() の結果が一致する"""
        from repom.config import RepomConfig
        config = RepomConfig(exec_env='prod')
        config.db_type = 'postgres'
        config.postgres.host = 'db.example.com'
        config.postgres.sslmode = 'verify-full'

        tls = config.postgres_tls_settings()

        assert f"sslmode={tls.sslmode}" in config.db_url
