"""PostgreSQL manage.py の単体テスト

DockerService, Volume 生成、および docker-compose.yml ファイル出力の機能をテストします。
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from repom.config import RepomConfig, PostgresConfig, PgAdminConfig
from repom._.docker_compose import DockerService, DockerVolume

DATA_PATH = Path("data") / "repom"


class TestGenerateDockerComposePostgresOnly:
    """generate_docker_compose() - PostgreSQL のみ（pgAdmin 無効）"""

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.get_init_dir')
    def test_postgres_only_service_generation(self, mock_get_init_dir, mock_config):
        """PostgreSQL のみのサービスが生成されることを確認"""
        # Mock setup
        mock_init_dir = Path("/tmp/init")
        mock_get_init_dir.return_value = mock_init_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "repom_dev"
        mock_pg_config.database = None

        mock_container_config = MagicMock()
        mock_container_config.get_container_name.return_value = "repom_postgres"
        mock_container_config.get_volume_name.return_value = "repom_postgres_data"
        mock_container_config.image = "postgres:16-alpine"
        mock_container_config.host_port = 5432

        mock_pg_config.container = mock_container_config

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False  # ← 無効

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = DATA_PATH

        # import and test
        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()

        # Assertions
        assert len(generator.services) == 1  # PostgreSQL のみ
        assert generator.services[0].name == "postgres"
        assert generator.services[0].image == "postgres:16-alpine"
        assert generator.services[0].container_name == "repom_postgres"
        assert generator.services[0].depends_on is None  # 依存なし


class TestGenerateDockerComposePgAdminEnabled:
    """generate_docker_compose() - pgAdmin 有効"""

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.get_init_dir')
    def test_postgres_and_pgadmin_service_generation(self, mock_get_init_dir, mock_config):
        """PostgreSQL と pgAdmin の両サービスが生成されることを確認"""
        # Mock setup
        mock_init_dir = Path("/tmp/init")
        mock_get_init_dir.return_value = mock_init_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "repom_dev"
        mock_pg_config.database = "myproject"

        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "myproject_postgres"
        mock_pg_container.get_volume_name.return_value = "myproject_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5433

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_container = MagicMock()
        mock_pgadmin_container.enabled = True  # ← 有効
        mock_pgadmin_container.get_container_name.return_value = "myproject_pgadmin"
        mock_pgadmin_container.get_volume_name.return_value = "myproject_pgadmin_data"
        mock_pgadmin_container.image = "dpage/pgadmin4:latest"
        mock_pgadmin_container.host_port = 5051

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.email = "admin@myproject.local"
        mock_pgadmin_config.password = "secure_pass"
        mock_pgadmin_config.container = mock_pgadmin_container

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = DATA_PATH

        # import and test
        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()

        # Assertions
        assert len(generator.services) == 2  # PostgreSQL + pgAdmin
        assert generator.services[0].name == "postgres"
        assert generator.services[1].name == "pgadmin"

        # pgAdmin の depends_on を確認
        pgadmin_service = generator.services[1]
        assert pgadmin_service.depends_on is not None
        assert "postgres" in pgadmin_service.depends_on
        assert pgadmin_service.depends_on["postgres"]["condition"] == "service_healthy"

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.get_init_dir')
    def test_pgadmin_yaml_generation(self, mock_get_init_dir, mock_config):
        """pgAdmin の YAML 出力が正しく生成されることを確認"""
        # Mock setup
        mock_init_dir = Path("/tmp/init")
        mock_get_init_dir.return_value = mock_init_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "repom_dev"
        mock_pg_config.database = None

        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.healthcheck = None

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_container = MagicMock()
        mock_pgadmin_container.enabled = True
        mock_pgadmin_container.get_container_name.return_value = "repom_pgadmin"
        mock_pgadmin_container.get_volume_name.return_value = "repom_pgadmin_data"
        mock_pgadmin_container.image = "dpage/pgadmin4:latest"
        mock_pgadmin_container.host_port = 5050

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.email = "admin@localhost"
        mock_pgadmin_config.password = "admin"
        mock_pgadmin_config.container = mock_pgadmin_container

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = DATA_PATH

        # import and test
        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()
        yaml_content = generator.generate()

        # YAML 出力確認
        assert "  pgadmin:" in yaml_content
        assert "    image: dpage/pgadmin4:latest" in yaml_content
        assert "    container_name: repom_pgadmin" in yaml_content
        assert "      PGADMIN_DEFAULT_EMAIL: admin@localhost" in yaml_content
        assert "      PGADMIN_DEFAULT_PASSWORD: admin" in yaml_content
        assert "      - \"5050:80\"" in yaml_content
        assert "    depends_on:" in yaml_content
        assert "      postgres:" in yaml_content


class TestGenerateInitSql:
    """generate_init_sql() - DB 初期化スクリプト生成"""

    @patch('repom.postgres.manage.config')
    def test_default_database_names(self, mock_config):
        """デフォルトの DB 名（repom_dev, repom_test, repom_prod）が生成されることを確認"""
        mock_config.data_path = DATA_PATH
        mock_config.postgres.database = None  # デフォルト
        mock_config.postgres.user = "repom"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        # 全環境の CREATE DATABASE が含まれる
        assert "CREATE DATABASE repom_dev;" in sql
        assert "CREATE DATABASE repom_test;" in sql
        assert "CREATE DATABASE repom_prod;" in sql
        # GRANT もすべての DB に対して含まれる
        assert "GRANT ALL PRIVILEGES ON DATABASE repom_dev TO repom;" in sql
        assert "GRANT ALL PRIVILEGES ON DATABASE repom_test TO repom;" in sql
        assert "GRANT ALL PRIVILEGES ON DATABASE repom_prod TO repom;" in sql

    @patch('repom.postgres.manage.config')
    def test_custom_database_names(self, mock_config):
        """カスタム DB 名（mine_py_dev, mine_py_test, mine_py_prod）が生成されることを確認"""
        mock_config.data_path = DATA_PATH
        mock_config.postgres.database = "mine_py"  # カスタム
        mock_config.postgres.user = "mine_py"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        # 全環境の CREATE DATABASE が含まれる
        assert "CREATE DATABASE mine_py_dev;" in sql
        assert "CREATE DATABASE mine_py_test;" in sql
        assert "CREATE DATABASE mine_py_prod;" in sql
        # GRANT もすべての DB に対して含まれる
        assert "GRANT ALL PRIVILEGES ON DATABASE mine_py_dev TO mine_py;" in sql
        assert "GRANT ALL PRIVILEGES ON DATABASE mine_py_test TO mine_py;" in sql
        assert "GRANT ALL PRIVILEGES ON DATABASE mine_py_prod TO mine_py;" in sql

    @patch('repom.postgres.manage.config')
    def test_environment_prefixing_in_sql(self, mock_config):
        """環境別にデータベース名が正しくプレフィックスされていることを確認"""
        mock_config.data_path = DATA_PATH
        mock_config.postgres.database = "project"
        mock_config.postgres.user = "user"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        # 全環境の CREATE DATABASE が含まれる
        assert "CREATE DATABASE project_dev;" in sql
        assert "CREATE DATABASE project_test;" in sql
        assert "CREATE DATABASE project_prod;" in sql

        # 全環境に対して GRANT が発行される
        assert "GRANT ALL PRIVILEGES ON DATABASE project_dev TO user;" in sql
        assert "GRANT ALL PRIVILEGES ON DATABASE project_test TO user;" in sql
        assert "GRANT ALL PRIVILEGES ON DATABASE project_prod TO user;" in sql


class TestDockerComposeFileGeneration:
    """Compose ファイルのファイル出力テスト"""

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.get_compose_dir')
    @patch('repom.postgres.manage.get_init_dir')
    def test_yaml_file_is_valid(self, mock_get_init_dir, mock_get_compose_dir, mock_config, tmp_path):
        """生成される YAML ファイルが有効な形式であることを確認"""
        # Mock setup
        mock_init_dir = tmp_path / "init"
        mock_init_dir.mkdir()
        mock_get_init_dir.return_value = mock_init_dir

        mock_compose_dir = tmp_path / "compose"
        mock_compose_dir.mkdir()
        mock_get_compose_dir.return_value = mock_compose_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "repom_dev"
        mock_pg_config.database = None

        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = DATA_PATH

        # Test
        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()
        yaml_content = generator.generate()

        # YAML の基本構造を確認
        assert "version: '3.8'" in yaml_content
        assert "services:" in yaml_content
        assert "volumes:" in yaml_content
        assert "  postgres:" in yaml_content
        assert "  repom_postgres_data:" in yaml_content

        # 重要な設定確認
        assert "POSTGRES_USER: repom" in yaml_content
        assert "POSTGRES_PASSWORD: repom_dev" in yaml_content
        # Note: POSTGRES_DB は省略される（環境別DBは init スクリプトで作成）
        assert "POSTGRES_DB" not in yaml_content


class TestPgAdminServersJson:
    """pgAdmin servers.json 設定ファイル生成のテスト"""

    @patch('repom.postgres.manage.config')
    def test_generate_pgadmin_servers_json(self, mock_config):
        """servers.json 設定の生成テスト - デフォルト値"""
        # Mock setup
        mock_config.data_path = DATA_PATH
        mock_config.postgres.user = "repom"
        mock_config.postgres.password = "repom_dev"
        mock_config.postgres.database = None  # デフォルト
        mock_config.postgres.container.get_container_name.return_value = "repom_postgres"

        from repom.postgres.manage import generate_pgadmin_servers_json

        # Test
        config_dict = generate_pgadmin_servers_json()

        # Assertions
        assert "Servers" in config_dict
        assert "1" in config_dict["Servers"]
        server = config_dict["Servers"]["1"]
        assert server["Name"] == "repom_postgres"
        assert server["Host"] == "postgres"
        assert server["Port"] == 5432
        assert server["Username"] == "repom"
        assert server["SSLMode"] == "prefer"
        assert server["MaintenanceDB"] == "repom_dev"  # デフォルト

    @patch('repom.postgres.manage.config')
    def test_generate_pgadmin_servers_json_custom_config(self, mock_config):
        """servers.json 設定の生成テスト - カスタム値（CONFIG_HOOK 想定）"""
        # Mock setup - 外部プロジェクトの CONFIG_HOOK を想定
        mock_config.data_path = DATA_PATH
        mock_config.postgres.user = "mine_py"
        mock_config.postgres.password = "mine_py_dev"
        mock_config.postgres.database = "mine_py"
        mock_config.postgres.container.get_container_name.return_value = "mine_py_postgres"

        from repom.postgres.manage import generate_pgadmin_servers_json

        # Test
        config_dict = generate_pgadmin_servers_json()

        # Assertions
        server = config_dict["Servers"]["1"]
        assert server["Name"] == "mine_py_postgres"  # カスタムコンテナ名
        assert server["Host"] == "postgres"  # Docker network 内は常に "postgres"
        assert server["Username"] == "mine_py"
        assert server["MaintenanceDB"] == "mine_py_dev"  # カスタム DB 名

class TestDirectorySeparation:
    """Tests for separate project directory structure (Issue #043)"""

    def test_get_compose_dir_uses_postgres_subdir(self):
        """get_compose_dir が postgres サブディレクトリを使用（分離プロジェクト構造）"""
        from repom.postgres.manage import get_compose_dir
        from repom.config import config

        compose_dir = get_compose_dir()
        
        # Should be config.data_path/postgres/
        assert str(compose_dir).endswith("postgres")
        assert "postgres" in str(compose_dir)

    def test_postgres_generate_creates_in_postgres_subdir(self):
        """postgres_generate が data/repom/postgres/ に docker-compose.yml を生成"""
        from repom.postgres.manage import generate, get_compose_dir

        # Generate files
        generate()

        # Verify files are in postgres subdirectory
        compose_file = get_compose_dir() / "docker-compose.generated.yml"
        assert compose_file.exists()
        assert "postgres" in str(compose_file.parent)

    def test_postgres_redis_no_conflict(self):
        """postgres_generate と redis_generate の両方実行時に競合しない"""
        from repom.postgres.manage import generate as postgres_generate, get_compose_dir as get_postgres_compose_dir
        from repom.redis.manage import generate as redis_generate, get_compose_dir as get_redis_compose_dir

        # Generate both
        postgres_generate()
        redis_generate()

        # Verify both files exist in their respective directories
        postgres_compose = get_postgres_compose_dir() / "docker-compose.generated.yml"
        redis_compose = get_redis_compose_dir() / "docker-compose.generated.yml"

        assert postgres_compose.exists()
        assert redis_compose.exists()

        # Verify they are in different directories
        assert postgres_compose.parent != redis_compose.parent
        assert "postgres" in str(postgres_compose)
        assert "redis" in str(redis_compose)

        # Verify Redis file doesn't contain postgres references
        redis_content = redis_compose.read_text()
        assert "postgres" not in redis_content.lower()
        assert "pgadmin" not in redis_content.lower()