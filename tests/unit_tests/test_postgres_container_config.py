"""PostgresContainerConfig の単体テスト"""

import pytest
from repom.config import PostgresContainerConfig, PostgresConfig, RepomConfig


class TestPostgresContainerConfig:
    """PostgresContainerConfig のテスト"""

    def test_default_values(self):
        """デフォルト値を確認"""
        container = PostgresContainerConfig()

        assert container.project_name == "repom"
        assert container.container_name is None
        assert container.host_port == 5432
        assert container.volume_name is None
        assert container.image == "postgres:16-alpine"

    def test_get_container_name_default(self):
        """デフォルトのコンテナ名を取得"""
        container = PostgresContainerConfig()

        assert container.get_container_name() == "repom_postgres"

    def test_get_container_name_custom_project(self):
        """カスタムプロジェクト名でコンテナ名を取得"""
        container = PostgresContainerConfig(project_name="mine_py")

        assert container.get_container_name() == "mine_py_postgres"

    def test_get_container_name_explicit(self):
        """明示的に指定したコンテナ名を取得"""
        container = PostgresContainerConfig(
            project_name="mine_py",
            container_name="custom_container"
        )

        assert container.get_container_name() == "custom_container"

    def test_get_volume_name_default(self):
        """デフォルトのVolume名を取得"""
        container = PostgresContainerConfig()

        assert container.get_volume_name() == "repom_postgres_data"

    def test_get_volume_name_custom_project(self):
        """カスタムプロジェクト名でVolume名を取得"""
        container = PostgresContainerConfig(project_name="mine_py")

        assert container.get_volume_name() == "mine_py_postgres_data"

    def test_get_volume_name_explicit(self):
        """明示的に指定したVolume名を取得"""
        container = PostgresContainerConfig(
            project_name="mine_py",
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

        assert config.container.project_name == "repom"
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

        assert config.postgres.container.project_name == "repom"
        assert config.postgres.container.get_container_name() == "repom_postgres"
        assert config.postgres.container.get_volume_name() == "repom_postgres_data"
        assert config.postgres.container.host_port == 5432
        assert config.postgres.container.image == "postgres:16-alpine"

    def test_hook_pattern_simulation(self):
        """CONFIG_HOOK でのカスタマイズパターンをシミュレート"""
        config = RepomConfig()

        # mine-py プロジェクトの設定をシミュレート
        config.postgres.container.project_name = "mine_py"
        config.postgres.container.host_port = 5433
        config.postgres.user = "mine_py"
        config.postgres.password = "mine_py_dev"

        # 検証
        assert config.postgres.container.get_container_name() == "mine_py_postgres"
        assert config.postgres.container.get_volume_name() == "mine_py_postgres_data"
        assert config.postgres.container.host_port == 5433
        assert config.postgres.user == "mine_py"
        assert config.postgres.password == "mine_py_dev"

    def test_multiple_project_patterns(self):
        """複数プロジェクトのパターンを確認"""
        # repom
        config_repom = RepomConfig()
        assert config_repom.postgres.container.get_container_name() == "repom_postgres"
        assert config_repom.postgres.container.host_port == 5432

        # mine-py
        config_mine = RepomConfig()
        config_mine.postgres.container.project_name = "mine_py"
        config_mine.postgres.container.host_port = 5433
        assert config_mine.postgres.container.get_container_name() == "mine_py_postgres"
        assert config_mine.postgres.container.host_port == 5433

        # fast-domain
        config_fast = RepomConfig()
        config_fast.postgres.container.project_name = "fast_domain"
        config_fast.postgres.container.host_port = 5434
        assert config_fast.postgres.container.get_container_name() == "fast_domain_postgres"
        assert config_fast.postgres.container.host_port == 5434
