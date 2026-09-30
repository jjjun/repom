"""PostgreSQL manage.py の単体テスト

DockerService, Volume 生成、および docker-compose.yml ファイル出力の機能をテストします。
"""

import os
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
from basekit.docker_manager import DockerCommandExecutor
from repom.postgres import manage
from repom.postgres.manage import PostgresManager

class TestGenerateDockerComposePostgresOnly:
    """generate_docker_compose() - PostgreSQL のみ（pgAdmin 無効）"""

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_postgres_only_service_generation(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
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
        mock_container_config.expose_to_lan = False

        mock_pg_config.container = mock_container_config

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False  # ← 無効

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

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
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_postgres_and_pgadmin_service_generation(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
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
        mock_pg_container.expose_to_lan = False

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_container = MagicMock()
        mock_pgadmin_container.enabled = True  # ← 有効
        mock_pgadmin_container.get_container_name.return_value = "myproject_pgadmin"
        mock_pgadmin_container.get_volume_name.return_value = "myproject_pgadmin_data"
        mock_pgadmin_container.image = "dpage/pgadmin4:latest"
        mock_pgadmin_container.host_port = 5051
        mock_pgadmin_container.expose_to_lan = False

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.email = "admin@myproject.local"
        mock_pgadmin_config.password = "secure_pass"
        mock_pgadmin_config.container = mock_pgadmin_container

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

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
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_pgadmin_yaml_generation(self, mock_get_init_dir, mock_config, tmp_path):
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
        mock_pg_container.expose_to_lan = False

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_container = MagicMock()
        mock_pgadmin_container.enabled = True
        mock_pgadmin_container.get_container_name.return_value = "repom_pgadmin"
        mock_pgadmin_container.get_volume_name.return_value = "repom_pgadmin_data"
        mock_pgadmin_container.image = "dpage/pgadmin4:latest"
        mock_pgadmin_container.host_port = 5050
        mock_pgadmin_container.expose_to_lan = False

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.email = "admin@localhost"
        mock_pgadmin_config.password = "pgadmin-secret"
        mock_pgadmin_config.container = mock_pgadmin_container

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        # import and test
        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()
        yaml_content = generator.generate()

        # YAML 出力確認
        assert "  pgadmin:" in yaml_content
        assert "    image: dpage/pgadmin4:latest" in yaml_content
        assert "    container_name: repom_pgadmin" in yaml_content
        assert '      PGADMIN_DEFAULT_EMAIL: "admin@localhost"' in yaml_content
        assert '      PGADMIN_DEFAULT_PASSWORD: "${PGADMIN_DEFAULT_PASSWORD}"' in yaml_content
        assert "pgadmin-secret" not in yaml_content
        assert "      - \"127.0.0.1:5050:80\"" in yaml_content
        assert "    depends_on:" in yaml_content
        assert "      postgres:" in yaml_content


class TestGenerateInitSql:
    """generate_init_sql() - DB 初期化スクリプト生成"""

    @patch('repom.postgres.manage.config')
    def test_default_database_names(self, mock_config, tmp_path):
        """デフォルトの DB 名（repom, repom_dev, repom_test）が生成されることを確認"""
        mock_config.data_path = tmp_path / "data" / "repom"
        mock_config.db_name = "repom"  # db_name を使用
        mock_config.postgres.user = "repom"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        # 全環境の CREATE DATABASE が含まれる（\gexec パターン）
        assert "'CREATE DATABASE \"repom\"'" in sql
        assert "'CREATE DATABASE \"repom_dev\"'" in sql
        assert "'CREATE DATABASE \"repom_test\"'" in sql
        # IF NOT EXISTS パターンが含まれる
        assert "WHERE NOT EXISTS" in sql
        assert "pg_database" in sql
        # GRANT もすべての DB に対して含まれる
        assert 'GRANT ALL PRIVILEGES ON DATABASE "repom" TO "repom";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "repom_dev" TO "repom";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "repom_test" TO "repom";' in sql

    @patch('repom.postgres.manage.config')
    def test_custom_database_names(self, mock_config, tmp_path):
        """カスタム DB 名（mine_py, mine_py_dev, mine_py_test）が生成されることを確認"""
        mock_config.data_path = tmp_path / "data" / "repom"
        mock_config.db_name = "mine_py"  # db_name を使用
        mock_config.postgres.user = "mine_py"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        # 全環境の CREATE DATABASE が含まれる（\gexec パターン）
        assert "'CREATE DATABASE \"mine_py\"'" in sql
        assert "'CREATE DATABASE \"mine_py_dev\"'" in sql
        assert "'CREATE DATABASE \"mine_py_test\"'" in sql
        # GRANT もすべての DB に対して含まれる
        assert 'GRANT ALL PRIVILEGES ON DATABASE "mine_py" TO "mine_py";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "mine_py_dev" TO "mine_py";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "mine_py_test" TO "mine_py";' in sql

    @patch('repom.postgres.manage.config')
    def test_environment_prefixing_in_sql(self, mock_config, tmp_path):
        """環境別にデータベース名が正しくプレフィックスされていることを確認"""
        mock_config.data_path = tmp_path / "data" / "repom"
        mock_config.db_name = "project"  # db_name を使用
        mock_config.postgres.user = "user"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        # 全環境の CREATE DATABASE が含まれる（\gexec パターン）
        assert "'CREATE DATABASE \"project\"'" in sql
        assert "'CREATE DATABASE \"project_dev\"'" in sql
        assert "'CREATE DATABASE \"project_test\"'" in sql

        # 全環境に対して GRANT が発行される
        assert 'GRANT ALL PRIVILEGES ON DATABASE "project" TO "user";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "project_dev" TO "user";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "project_test" TO "user";' in sql

    @patch('repom.postgres.manage.config')
    def test_hostile_database_and_user_names_are_quoted(self, mock_config, tmp_path):
        """Identifiers and literals are quoted in generated init SQL."""
        mock_config.data_path = tmp_path / "data" / "repom"
        mock_config.db_name = "app-db'oops"
        mock_config.postgres.user = 'app"user'

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        assert "CREATE DATABASE \"app-db''oops\"" in sql
        assert "datname = 'app-db''oops'" in sql
        assert (
            'GRANT ALL PRIVILEGES ON DATABASE "app-db\'oops" TO "app""user";'
            in sql
        )
        assert "-- app-db'oops" not in sql


class TestDockerComposeFileGeneration:
    """Compose ファイルのファイル出力テスト"""

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_compose_dir')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
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
        mock_pg_container.expose_to_lan = False

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        # Test
        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()
        yaml_content = generator.generate()

        compose = yaml.safe_load(yaml_content)

        assert compose["services"]["postgres"]["image"] == "postgres:16-alpine"
        assert compose["services"]["postgres"]["container_name"] == "repom_postgres"
        assert compose["services"]["postgres"]["environment"]["POSTGRES_USER"] == "repom"
        assert (
            compose["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"]
            == "${POSTGRES_PASSWORD}"
        )
        assert "repom_dev" not in yaml_content
        assert "POSTGRES_DB" not in compose["services"]["postgres"]["environment"]
        assert "repom_postgres_data" in compose["volumes"]

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generated_compose_has_no_plaintext_password(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
        """The generated compose file never contains the raw password value."""
        mock_init_dir = Path("/tmp/init")
        mock_get_init_dir.return_value = mock_init_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "s3cret-postgres-password"
        mock_pg_config.database = None

        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.expose_to_lan = False

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()
        yaml_content = generator.generate()

        assert "s3cret-postgres-password" not in yaml_content
        assert '"${POSTGRES_PASSWORD}"' in yaml_content

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generate_docker_compose_rejects_newline_in_password(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
        """A newline in the password cannot inject an extra YAML key."""
        mock_init_dir = Path("/tmp/init")
        mock_get_init_dir.return_value = mock_init_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "hostile\nPOSTGRES_HOST_AUTH_METHOD: trust"
        mock_pg_config.database = None

        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.expose_to_lan = False

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate_docker_compose

        with pytest.raises(ValueError, match="postgres.password"):
            generate_docker_compose()

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_healthcheck_uses_exec_form(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
        """The PostgreSQL healthcheck is an exec-form list, not CMD-SHELL."""
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
        mock_pg_container.expose_to_lan = False

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()
        test = generator.services[0].healthcheck["test"]

        assert test.startswith('["CMD",')
        assert "CMD-SHELL" not in test

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generated_ports_bind_loopback_by_default(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
        """Published ports bind to loopback unless expose_to_lan is set."""
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
        mock_pg_container.expose_to_lan = False

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()

        for port in generator.services[0].ports:
            assert port.startswith("127.0.0.1:")

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generated_ports_expose_to_lan_when_opted_in(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
        """expose_to_lan=True publishes the port on every interface."""
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
        mock_pg_container.expose_to_lan = True

        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()

        assert generator.services[0].ports == ["0.0.0.0:5432:5432"]

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generate_rejects_control_characters_in_identifiers(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
        """A newline in POSTGRES_USER or the container name raises."""
        mock_init_dir = Path("/tmp/init")
        mock_get_init_dir.return_value = mock_init_dir

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        mock_pg_config = MagicMock()
        mock_pg_config.password = "repom_dev"
        mock_pg_config.database = None
        mock_pg_container = MagicMock()
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.expose_to_lan = False
        mock_pg_config.container = mock_pg_container
        mock_config.postgres = mock_pg_config

        from repom.postgres.manage import generate_docker_compose

        mock_pg_config.user = "repom\nPOSTGRES_HOST_AUTH_METHOD: trust"
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        with pytest.raises(ValueError, match="postgres.user"):
            generate_docker_compose()

        mock_pg_config.user = "repom"
        mock_pg_container.get_container_name.return_value = "repom_postgres\nprivileged: true"
        with pytest.raises(ValueError, match="postgres.container.container_name"):
            generate_docker_compose()

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_compose_dir')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generate_stdout_does_not_include_passwords(
        self,
        mock_get_init_dir,
        mock_get_compose_dir,
        mock_config,
        tmp_path,
        capsys,
    ):
        """postgres_generate output does not print raw secrets."""
        mock_init_dir = tmp_path / "init"
        mock_init_dir.mkdir()
        mock_get_init_dir.return_value = mock_init_dir

        mock_compose_dir = tmp_path / "compose"
        mock_compose_dir.mkdir()
        mock_get_compose_dir.return_value = mock_compose_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "postgres-secret"
        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.expose_to_lan = False
        mock_pg_config.container = mock_pg_container

        mock_pgadmin_container = MagicMock()
        mock_pgadmin_container.enabled = True
        mock_pgadmin_container.get_container_name.return_value = "repom_pgadmin"
        mock_pgadmin_container.get_volume_name.return_value = "repom_pgadmin_data"
        mock_pgadmin_container.image = "dpage/pgadmin4:latest"
        mock_pgadmin_container.host_port = 5050
        mock_pgadmin_container.expose_to_lan = False
        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.email = "admin@example.com"
        mock_pgadmin_config.password = "pgadmin-secret"
        mock_pgadmin_config.container = mock_pgadmin_container

        mock_config.db_name = "repom"
        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate

        generate()

        captured = capsys.readouterr()
        assert "postgres-secret" not in captured.out
        assert "pgadmin-secret" not in captured.out

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_compose_dir')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generate_writes_password_to_env_file(
        self,
        mock_get_init_dir,
        mock_get_compose_dir,
        mock_config,
        tmp_path,
    ):
        """The password is written to a .env secrets file, not the compose file."""
        mock_init_dir = tmp_path / "init"
        mock_init_dir.mkdir()
        mock_get_init_dir.return_value = mock_init_dir

        mock_compose_dir = tmp_path / "compose"
        mock_compose_dir.mkdir()
        mock_get_compose_dir.return_value = mock_compose_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "postgres-secret"
        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.expose_to_lan = False
        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.db_name = "repom"
        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import COMPOSE_FILENAME, generate

        generate()

        compose_content = (mock_compose_dir / COMPOSE_FILENAME).read_text()
        assert "postgres-secret" not in compose_content

        env_content = (mock_compose_dir / ".env").read_text()
        assert env_content == 'POSTGRES_PASSWORD="postgres-secret"\n'

    @pytest.mark.skipif(
        os.name != "posix",
        reason="POSIX permission bits are not enforced on Windows",
    )
    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_compose_dir')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generated_env_file_is_0600(
        self,
        mock_get_init_dir,
        mock_get_compose_dir,
        mock_config,
        tmp_path,
    ):
        """The generated .env secrets file is owner-read/write only."""
        mock_init_dir = tmp_path / "init"
        mock_init_dir.mkdir()
        mock_get_init_dir.return_value = mock_init_dir

        mock_compose_dir = tmp_path / "compose"
        mock_compose_dir.mkdir()
        mock_get_compose_dir.return_value = mock_compose_dir

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "postgres-secret"
        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.expose_to_lan = False
        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = False

        mock_config.db_name = "repom"
        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate

        generate()

        env_file = mock_compose_dir / ".env"
        assert stat.S_IMODE(env_file.stat().st_mode) == 0o600


class TestPgAdminServersJson:
    """pgAdmin servers.json 設定ファイル生成のテスト"""

    @patch('repom.postgres.manage.config')
    def test_generate_pgadmin_servers_json(self, mock_config, tmp_path):
        """servers.json 設定の生成テスト - デフォルト値"""
        # Mock setup
        mock_config.data_path = tmp_path / "data" / "repom"
        mock_config.postgres.user = "repom"
        mock_config.postgres.password = "repom_dev"
        mock_config.db_name = "repom"  # db_name を使用
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
    def test_generate_pgadmin_servers_json_custom_config(self, mock_config, tmp_path):
        """servers.json 設定の生成テスト - カスタム値（CONFIG_HOOK 想定）"""
        # Mock setup - 外部プロジェクトの CONFIG_HOOK を想定
        mock_config.data_path = tmp_path / "data" / "repom"
        mock_config.postgres.user = "mine_py"
        mock_config.postgres.password = "mine_py_dev"
        mock_config.db_name = "mine_py"  # db_name を使用
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

    def test_postgres_generate_creates_in_postgres_subdir(self, tmp_path):
        """postgres_generate が data/repom/postgres/ に docker-compose.yml を生成"""
        from repom.postgres import manage as postgres_manage
        from repom.postgres.manage import PostgresManager, generate

        compose_dir = tmp_path / "postgres"
        compose_dir.mkdir()
        init_dir = compose_dir / "postgresql_init"
        init_dir.mkdir()

        # Generate files. Patching the manage module's own config reference
        # (rather than a freshly re-imported repom.config.config) keeps this
        # correct even if another test reloaded repom.config first.
        with (
            patch.object(postgres_manage.config.postgres, "password", "test-postgres-password"),
            patch.object(postgres_manage.config.pgadmin, "password", "test-pgadmin-password"),
            patch.object(PostgresManager, "get_compose_dir", return_value=compose_dir),
            patch.object(PostgresManager, "get_init_dir", return_value=init_dir),
        ):
            generate()

        # Verify files are in postgres subdirectory
        compose_file = compose_dir / "docker-compose.generated.yml"
        assert compose_file.exists()
        assert "postgres" in str(compose_file.parent)

    def test_generate_refuses_changed_credentials_and_force_keeps_backup(self, tmp_path):
        from repom.postgres import manage

        mock_config = MagicMock()
        mock_config.db_name = "repom"
        mock_config.postgres.password = "postgres-new-secret"
        mock_config.postgres.container.get_container_name.return_value = "repom_postgres"
        mock_config.postgres.container.get_volume_name.return_value = "repom_postgres_data"
        mock_config.postgres.container.host_port = 5432
        mock_config.pgadmin.container.enabled = True
        mock_config.pgadmin.password = "pgadmin-new-secret"
        mock_config.pgadmin.email = "admin@example.com"
        mock_config.pgadmin.container.get_container_name.return_value = "repom_pgadmin"
        mock_config.pgadmin.container.get_volume_name.return_value = "repom_pgadmin_data"
        mock_config.pgadmin.container.host_port = 5050

        compose_dir = tmp_path / "postgres"
        compose_dir.mkdir()
        init_dir = compose_dir / "postgresql_init"
        init_dir.mkdir()
        env_file = compose_dir / ".env"
        original_env = (
            'POSTGRES_PASSWORD="postgres-old-secret"\n'
            'PGADMIN_DEFAULT_PASSWORD="pgadmin-old-secret"\n'
        )
        env_file.write_text(original_env, encoding="utf-8")

        with patch.object(manage, "config", mock_config):
            with patch.object(manage.PostgresManager, "get_compose_dir", return_value=compose_dir):
                with patch.object(manage.PostgresManager, "get_init_dir", return_value=init_dir):
                    with patch.object(manage, "generate_docker_compose") as generate_compose:
                        with patch.object(manage, "generate_init_sql", return_value="-- init\n"):
                            with patch.object(manage, "generate_pgadmin_servers_json", return_value={}):
                                with pytest.raises(ValueError) as excinfo:
                                    manage.generate()

                                assert "postgres_rotate_credentials" in str(excinfo.value)
                                assert "pgadmin_rotate_password" in str(excinfo.value)
                                assert "postgres-new-secret" not in str(excinfo.value)
                                assert "pgadmin-new-secret" not in str(excinfo.value)
                                assert env_file.read_text(encoding="utf-8") == original_env
                                generate_compose.return_value.write_to_file.assert_not_called()

                                manage.generate(overwrite_secrets=True)

        assert env_file.read_text(encoding="utf-8") == (
            'POSTGRES_PASSWORD="postgres-new-secret"\n'
            'PGADMIN_DEFAULT_PASSWORD="pgadmin-new-secret"\n'
        )
        assert (compose_dir / ".env.bak").read_text(encoding="utf-8") == original_env
        assert stat.S_IMODE((compose_dir / ".env.bak").stat().st_mode) == 0o600

    def test_postgres_redis_no_conflict(self, tmp_path):
        """postgres_generate と redis_generate の両方実行時に競合しない"""
        from repom.postgres import manage as postgres_manage
        from repom.postgres.manage import PostgresManager, generate as postgres_generate
        from repom.redis import manage as redis_manage
        from repom.redis.manage import RedisManager, generate as redis_generate

        postgres_compose_dir = tmp_path / "postgres"
        postgres_compose_dir.mkdir()
        postgres_init_dir = postgres_compose_dir / "postgresql_init"
        postgres_init_dir.mkdir()
        redis_compose_dir = tmp_path / "redis"
        redis_compose_dir.mkdir()
        redis_init_dir = redis_compose_dir / "redis_init"
        redis_init_dir.mkdir()

        # Generate both
        with (
            patch.object(postgres_manage.config.postgres, "password", "test-postgres-password"),
            patch.object(postgres_manage.config.pgadmin, "password", "test-pgadmin-password"),
            patch.object(redis_manage.config.redis, "password", "test-redis-password"),
            patch.object(PostgresManager, "get_compose_dir", return_value=postgres_compose_dir),
            patch.object(PostgresManager, "get_init_dir", return_value=postgres_init_dir),
            patch.object(RedisManager, "get_compose_dir", return_value=redis_compose_dir),
            patch.object(RedisManager, "get_init_dir", return_value=redis_init_dir),
        ):
            postgres_generate()
            redis_generate()

        # Verify both files exist in their respective directories
        postgres_compose = postgres_compose_dir / "docker-compose.generated.yml"
        redis_compose = redis_compose_dir / "docker-compose.generated.yml"

        assert postgres_compose.exists()
        assert redis_compose.exists()

        # Verify they are in different directories
        assert postgres_compose.parent != redis_compose.parent
        assert "postgres" in str(postgres_compose)
        assert "redis" in str(redis_compose)

        # Verify Redis file doesn't contain postgres references
        redis_content = redis_compose.read_text()
        assert "  postgres:" not in redis_content.lower()
        assert "pgadmin" not in redis_content.lower()

    def test_module_level_directory_helpers_are_removed(self):
        """module-level get_compose_dir/get_init_dir are no longer public."""
        import pytest

        with pytest.raises(ImportError):
            from repom.postgres.manage import get_compose_dir  # noqa: F401

        with pytest.raises(ImportError):
            from repom.postgres.manage import get_init_dir  # noqa: F401


class TestPostgresManagerName:
    def test_get_container_name_uses_config(self):
        manager = PostgresManager()

        assert manager.config is manage.config
        assert manager.get_container_name() == (
            manage.config.postgres.container.get_container_name()
        )


class TestPostgresManagerWaitForService:
    @pytest.fixture(autouse=True)
    def _patch_readiness_sleep(self):
        with patch("basekit.docker_manager.time.sleep") as sleep:
            yield sleep

    def test_wait_for_service_immediate_success(self, _patch_readiness_sleep):
        manager = PostgresManager()

        with patch("repom.postgres.manage.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)

            manager.wait_for_service(max_retries=2)

        assert run.call_count == 1
        _patch_readiness_sleep.assert_not_called()

    def test_wait_for_service_timeout(self, _patch_readiness_sleep):
        manager = PostgresManager()

        with patch("repom.postgres.manage.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1)

            with pytest.raises(TimeoutError):
                manager.wait_for_service(max_retries=1)

        assert _patch_readiness_sleep.call_count == 1


class TestPostgresManagerConnectionInfo:
    def test_print_connection_info(self, capsys):
        manager = PostgresManager()

        manager.print_connection_info()

        output = capsys.readouterr().out
        assert "PostgreSQL Connection" in output
        assert "127.0.0.1" in output
        assert str(manager.config.postgres.container.host_port) in output

    def test_print_connection_info_masks_passwords(self, capsys):
        mock_config = MagicMock()
        mock_config.data_path = Path("data") / "repom"
        mock_config.db_name = "repom"
        mock_config.postgres.user = "repom"
        mock_config.postgres.password = "postgres-secret"
        mock_config.postgres.container.host_port = 5432
        mock_config.postgres.container.get_container_name.return_value = (
            "repom_postgres"
        )
        mock_config.pgadmin.email = "admin@example.com"
        mock_config.pgadmin.password = "pgadmin-secret"
        mock_config.pgadmin.container.enabled = True
        mock_config.pgadmin.container.host_port = 5050

        with patch("repom.postgres.manage.config", mock_config):
            manager = PostgresManager()
            manager.print_connection_info()

        output = capsys.readouterr().out
        assert "postgres-secret" not in output
        assert "pgadmin-secret" not in output
        assert output.count("Password: ***") == 2


@pytest.mark.parametrize(
    ("entrypoint", "compose_command"),
    [
        pytest.param(manage.start, "up -d", id="start"),
        pytest.param(manage.stop, "stop", id="stop"),
        pytest.param(manage.remove, "down -v", id="remove"),
    ],
)
def test_lifecycle_entrypoints_run_expected_compose_command(
    entrypoint, compose_command, monkeypatch, tmp_path
):
    compose_file = tmp_path / "docker-compose.generated.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(
        PostgresManager, "get_compose_file_path", lambda self: compose_file
    )
    run_compose = MagicMock()
    monkeypatch.setattr(DockerCommandExecutor, "run_docker_compose", run_compose)

    if entrypoint is manage.start:
        generate = MagicMock()
        monkeypatch.setattr(manage, "generate", generate)
        monkeypatch.setattr(
            PostgresManager, "wait_for_service", lambda self, max_retries: None
        )

    entrypoint()

    if entrypoint is manage.start:
        generate.assert_called_once_with(overwrite_secrets=False)
    run_compose.assert_called_once_with(
        compose_command,
        compose_file,
        cwd=compose_file.parent,
        project_name=PostgresManager().get_container_name(),
    )


class TestPostgresEnsureRunning:
    """ensure_running() の単体テスト"""

    def _patch_config(self, *, pgadmin_enabled: bool):
        """`repom.postgres.manage.config` の MagicMock 差し替えを返す"""
        mock_config = MagicMock()
        mock_config.data_path = "/repom-test-data-does-not-exist"
        mock_config.postgres.container.get_container_name.return_value = "repom_postgres"
        mock_config.pgadmin.container.enabled = pgadmin_enabled
        mock_config.pgadmin.container.get_container_name.return_value = "repom_pgadmin"
        return mock_config

    def test_uses_existing_generated_files_when_postgres_is_down(self, tmp_path):
        from repom.postgres import manage

        mock_config = self._patch_config(pgadmin_enabled=False)
        compose_dir = tmp_path / "postgres"
        compose_dir.mkdir()
        (compose_dir / manage.COMPOSE_FILENAME).write_text("services: {}\n")
        (compose_dir / ".env").write_text('POSTGRES_PASSWORD="saved-secret"\n')
        manager_instance = MagicMock()
        manager_instance.get_compose_dir.return_value = compose_dir

        with patch.object(manage, "config", mock_config):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate") as generate:
                    with patch.object(manage, "PostgresManager", return_value=manager_instance):
                        manage.ensure_running()

        generate.assert_not_called()
        manager_instance.get_compose_dir.assert_called_once_with()
        manager_instance.start.assert_called_once_with(timeout_seconds=30)

    def test_returns_when_postgres_and_pgadmin_running(self):
        """postgres と pgAdmin の両方が起動済みなら何もしない"""
        from repom.postgres import manage

        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=True)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=True,
            ) as is_running:
                with patch.object(manage, "generate") as generate:
                    with patch.object(manage, "PostgresManager") as manager_cls:
                        manage.ensure_running()

        assert is_running.call_count == 2
        generate.assert_not_called()
        manager_cls.assert_not_called()

    def test_returns_when_postgres_running_and_pgadmin_disabled(self):
        """pgAdmin が無効なら postgres の状態だけで判定する"""
        from repom.postgres import manage

        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=False)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=True,
            ) as is_running:
                with patch.object(manage, "generate") as generate:
                    with patch.object(manage, "PostgresManager") as manager_cls:
                        manage.ensure_running()

        is_running.assert_called_once_with("repom_postgres")
        generate.assert_not_called()
        manager_cls.assert_not_called()

    def test_starts_when_postgres_down(self, tmp_path):
        """postgres が未起動なら generate + manager.start(timeout) を呼ぶ"""
        from repom.postgres import manage

        manager_instance = MagicMock()
        manager_instance.get_compose_dir.return_value = tmp_path / "postgres"
        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=False)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate") as generate:
                    with patch.object(
                        manage, "PostgresManager", return_value=manager_instance
                    ):
                        manage.ensure_running(timeout_seconds=42)

        generate.assert_called_once_with()
        manager_instance.start.assert_called_once_with(timeout_seconds=42)

    def test_starts_when_only_pgadmin_down(self, tmp_path):
        """postgres は up でも pgAdmin が down なら起動処理に入る"""
        from repom.postgres import manage

        manager_instance = MagicMock()
        manager_instance.get_compose_dir.return_value = tmp_path / "postgres"

        def is_container_running(name):
            return name == "repom_postgres"  # pgadmin は False

        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=True)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                side_effect=is_container_running,
            ):
                with patch.object(manage, "generate") as generate:
                    with patch.object(
                        manage, "PostgresManager", return_value=manager_instance
                    ):
                        manage.ensure_running()

        generate.assert_called_once_with()
        manager_instance.start.assert_called_once_with(timeout_seconds=30)

    def test_skips_pgadmin_check_when_include_pgadmin_false(self):
        """include_pgadmin=False なら pgAdmin の起動有無を見ない"""
        from repom.postgres import manage

        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=True)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=True,
            ) as is_running:
                with patch.object(manage, "generate") as generate:
                    with patch.object(manage, "PostgresManager") as manager_cls:
                        manage.ensure_running(include_pgadmin=False)

        is_running.assert_called_once_with("repom_postgres")
        generate.assert_not_called()
        manager_cls.assert_not_called()

class TestGenerateFailsClosedOnDefaultCredentials:
    """postgres_generate must not stand up a database with a known password."""

    @pytest.mark.parametrize(
        "password",
        [
            pytest.param(None, id="unset"),
            pytest.param("", id="empty"),
            pytest.param("CHANGE_ME", id="placeholder"),
        ],
    )
    def test_generate_rejects_unconfigured_postgres_password(
        self, password, monkeypatch, tmp_path
    ):
        init_dir = tmp_path / "init"
        init_dir.mkdir()
        mock_config = MagicMock()
        mock_config.data_path = tmp_path / "data" / "repom"
        mock_config.postgres.user = "repom"
        mock_config.postgres.password = password
        monkeypatch.setattr(manage, "config", mock_config)
        monkeypatch.setattr(
            PostgresManager, "get_init_dir", lambda self: init_dir
        )

        with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
            manage.generate()

        assert list(init_dir.iterdir()) == []

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_generate_rejects_pgadmin_default_password_when_enabled(
        self, mock_get_init_dir, mock_config, tmp_path
    ):
        """pgAdmin's admin@example.com / admin pair is rejected once enabled."""
        mock_get_init_dir.return_value = Path("/tmp/init")

        mock_pg_config = MagicMock()
        mock_pg_config.user = "repom"
        mock_pg_config.password = "a-real-postgres-password"
        mock_pg_container = MagicMock()
        mock_pg_container.get_container_name.return_value = "repom_postgres"
        mock_pg_container.get_volume_name.return_value = "repom_postgres_data"
        mock_pg_container.image = "postgres:16-alpine"
        mock_pg_container.host_port = 5432
        mock_pg_container.expose_to_lan = False
        mock_pg_config.container = mock_pg_container

        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.container.enabled = True
        mock_pgadmin_config.password = "CHANGE_ME"

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = tmp_path / "data" / "repom"

        from repom.postgres.manage import generate_docker_compose

        with pytest.raises(ValueError, match="PGADMIN_DEFAULT_PASSWORD"):
            generate_docker_compose()

class TestPostgresGenerationCLI:
    def test_force_regenerate_flag_is_forwarded_to_generate(self, monkeypatch):
        import sys

        from repom.postgres import manage

        monkeypatch.setattr(sys, "argv", ["postgres_generate", "--force-regenerate"])
        with patch.object(manage, "generate") as generate:
            manage.main_generate()

        generate.assert_called_once_with(overwrite_secrets=True)

    def test_force_regenerate_flag_is_forwarded_to_start(self, monkeypatch):
        import sys

        from repom.postgres import manage

        monkeypatch.setattr(sys, "argv", ["postgres_start", "--force-regenerate"])
        with patch.object(manage, "start") as start:
            manage.main_start()

        start.assert_called_once_with(overwrite_secrets=True)
