"""PostgresContainerConfig の単体テスト"""

import pytest
from repom.config import (
    PostgresContainerConfig, PostgresConfig, RepomConfig,
    PgAdminContainerConfig, PgAdminConfig
)


class TestPostgresContainerConfig:
    """PostgresContainerConfig のテスト"""

    def test_default_values(self):
        """デフォルト値を確認"""
        container = PostgresContainerConfig()

        assert container.container_name is None
        assert container.host_port == 5432
        assert container.volume_name is None
        assert container.image == "postgres:16-alpine"

    def test_get_container_name_default(self):
        """デフォルトのコンテナ名を取得"""
        container = PostgresContainerConfig()

        assert container.get_container_name() == "repom_postgres"

    def test_get_container_name_explicit(self):
        """明示的に指定したコンテナ名を取得"""
        container = PostgresContainerConfig(
            container_name="custom_container"
        )

        assert container.get_container_name() == "custom_container"

    def test_get_volume_name_default(self):
        """デフォルトのVolume名を取得"""
        container = PostgresContainerConfig()

        assert container.get_volume_name() == "repom_postgres_data"

    def test_get_volume_name_explicit(self):
        """明示的に指定したVolume名を取得"""
        container = PostgresContainerConfig(
            volume_name="custom_volume"
        )

        assert container.get_volume_name() == "custom_volume"

    def test_custom_port(self):
        """カスタムポートを設定"""
        container = PostgresContainerConfig(host_port=5433)

        assert container.host_port == 5433

    def test_custom_image(self):
        """カスタムイメージを設定"""
        container = PostgresContainerConfig(image="postgres:15-alpine")

        assert container.image == "postgres:15-alpine"


class TestPostgresConfig:
    """PostgresConfig のテスト（container フィールド追加後）"""

    def test_default_values(self):
        """デフォルト値を確認"""
        config = PostgresConfig()

        assert config.host == 'localhost'
        assert config.port == 5432
        assert config.user == 'repom'
        assert config.password == 'repom_dev'
        assert config.database is None
        assert isinstance(config.container, PostgresContainerConfig)

    def test_container_default(self):
        """デフォルトのコンテナ設定を確認"""
        config = PostgresConfig()

        assert config.container.get_container_name() == "repom_postgres"
        assert config.container.host_port == 5432

    def test_custom_values(self):
        """カスタム値を設定"""
        config = PostgresConfig(
            host='192.168.1.100',
            port=5433,
            user='mine_py',
            password='mine_py_dev'
        )

        assert config.host == '192.168.1.100'
        assert config.port == 5433
        assert config.user == 'mine_py'
        assert config.password == 'mine_py_dev'


class TestRepomConfigPostgres:
    """RepomConfig の PostgreSQL 設定テスト"""

    def test_default_postgres_config(self):
        """デフォルトの PostgreSQL 設定を確認"""
        config = RepomConfig()

        assert isinstance(config.postgres, PostgresConfig)
        assert config.postgres.host == 'localhost'
        assert config.postgres.port == 5432
        assert config.postgres.user == 'repom'
        assert isinstance(config.postgres.container, PostgresContainerConfig)

    def test_postgres_container_config(self):
        """PostgreSQL コンテナ設定を確認"""
        config = RepomConfig()

        assert config.postgres.container.get_container_name() == "repom_postgres"
        assert config.postgres.container.get_volume_name() == "repom_postgres_data"
        assert config.postgres.container.host_port == 5432
        assert config.postgres.container.image == "postgres:16-alpine"

    def test_hook_pattern_simulation(self):
        """CONFIG_HOOK でのカスタマイズパターンをシミュレート"""
        config = RepomConfig()

        # mine-py プロジェクトの設定をシミュレート
        config.postgres.container.container_name = "mine_py_postgres"
        config.postgres.container.host_port = 5433
        config.postgres.user = "mine_py"
        config.postgres.password = "mine_py_dev"

        # 検証
        assert config.postgres.container.get_container_name() == "mine_py_postgres"
        assert config.postgres.container.host_port == 5433
        assert config.postgres.user == "mine_py"
        assert config.postgres.password == "mine_py_dev"

    def test_custom_port_and_name(self):
        """カスタムポートと明示的なコンテナ名を設定"""
        config = RepomConfig()
        config.postgres.container.host_port = 5433
        config.postgres.container.container_name = "fast_domain_postgres"
        assert config.postgres.container.get_container_name() == "fast_domain_postgres"
        assert config.postgres.container.host_port == 5433


class TestPgAdminContainerConfig:
    """PgAdminContainerConfig のテスト"""

    def test_default_values(self):
        """デフォルト値を確認"""
        container = PgAdminContainerConfig()

        assert container.container_name is None
        assert container.host_port == 5050
        assert container.volume_name is None
        assert container.image == "dpage/pgadmin4:latest"
        assert container.enabled is False

    def test_get_container_name_default(self):
        """デフォルトのコンテナ名を取得"""
        container = PgAdminContainerConfig()

        assert container.get_container_name() == "repom_pgadmin"

    def test_get_container_name_explicit(self):
        """明示的に指定したコンテナ名を取得"""
        container = PgAdminContainerConfig(
            container_name="custom_pgadmin"
        )

        assert container.get_container_name() == "custom_pgadmin"

    def test_get_volume_name_default(self):
        """デフォルトのVolume名を取得"""
        container = PgAdminContainerConfig()

        assert container.get_volume_name() == "repom_pgadmin_data"

    def test_get_volume_name_explicit(self):
        """明示的に指定したVolume名を取得"""
        container = PgAdminContainerConfig(
            volume_name="custom_pgadmin_volume"
        )

        assert container.get_volume_name() == "custom_pgadmin_volume"

    def test_custom_port(self):
        """カスタムポートを設定"""
        container = PgAdminContainerConfig(host_port=5051)

        assert container.host_port == 5051

    def test_enabled_flag(self):
        """enabled フラグを設定"""
        container = PgAdminContainerConfig(enabled=True)

        assert container.enabled is True


class TestPgAdminConfig:
    """PgAdminConfig のテスト"""

    def test_default_values(self):
        """デフォルト値を確認"""
        admin = PgAdminConfig()

        assert admin.email == "admin@example.com"
        assert admin.password == "admin"
        assert isinstance(admin.container, PgAdminContainerConfig)

    def test_container_default(self):
        """デフォルトのコンテナ設定を確認"""
        admin = PgAdminConfig()

        assert admin.container.get_container_name() == "repom_pgadmin"
        assert admin.container.host_port == 5050
        assert admin.container.enabled is False

    def test_custom_values(self):
        """カスタム値を設定"""
        admin = PgAdminConfig(
            email="admin@myproject.local",
            password="strong_password"
        )

        assert admin.email == "admin@myproject.local"
        assert admin.password == "strong_password"

    def test_custom_container(self):
        """カスタムコンテナ設定"""
        admin = PgAdminConfig(
            email="admin@mine.local",
            password="mine_pass"
        )
        admin.container.enabled = True
        admin.container.host_port = 5051

        assert admin.container.enabled is True
        assert admin.container.host_port == 5051


class TestRepomConfigPgAdmin:
    """RepomConfig の pgAdmin 設定テスト"""

    def test_default_pgadmin_config(self):
        """デフォルトの pgAdmin 設定を確認"""
        config = RepomConfig()

        assert isinstance(config.pgadmin, PgAdminConfig)
        assert config.pgadmin.email == "admin@example.com"
        assert config.pgadmin.password == "admin"
        assert isinstance(config.pgadmin.container, PgAdminContainerConfig)

    def test_pgadmin_default_disabled(self):
        """デフォルトでは pgAdmin は無効（既存プロジェクト非影響）"""
        config = RepomConfig()

        assert config.pgadmin.container.enabled is False

    def test_pgadmin_enable_and_customize(self):
        """pgAdmin を有効化してカスタマイズ"""
        config = RepomConfig()

        # 有効化と設定
        config.pgadmin.container.enabled = True
        config.pgadmin.container.host_port = 5051
        config.pgadmin.container.container_name = "myproject_pgadmin"
        config.pgadmin.email = "admin@myproject.local"
        config.pgadmin.password = "secure_password"

        assert config.pgadmin.container.enabled is True
        assert config.pgadmin.container.host_port == 5051
        assert config.pgadmin.container.get_container_name() == "myproject_pgadmin"
        assert config.pgadmin.email == "admin@myproject.local"
        assert config.pgadmin.password == "secure_password"

    def test_hook_pattern_pgadmin(self):
        """CONFIG_HOOK でのメール・パスワード設定パターン"""
        config = RepomConfig()

        # mine-py プロジェクト用 pgAdmin 設定
        config.pgadmin.container.enabled = True
        config.pgadmin.email = "admin@mine-py.local"
        config.pgadmin.password = "mine_py_admin_pass"

        assert config.pgadmin.container.enabled is True
        assert config.pgadmin.email == "admin@mine-py.local"
        assert config.pgadmin.password == "mine_py_admin_pass"
