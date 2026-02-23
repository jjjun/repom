"""PostgresContainerConfig の単体テスト"""

import pytest
from repom.config import PostgresContainerConfig, PostgresConfig, RepomConfig


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
