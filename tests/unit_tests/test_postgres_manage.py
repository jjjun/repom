"""PostgreSQL manage.py 

DockerService, Volume  docker-compose.yml 
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

DATA_PATH = Path("data") / "repom"


class TestGenerateDockerComposePostgresOnly:
    """generate_docker_compose() - PostgreSQL gAdmin """

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_postgres_only_service_generation(self, mock_get_init_dir, mock_config):
        """PostgreSQL """
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
        mock_pgadmin_config.container.enabled = False  # 

        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = DATA_PATH

        # import and test
        from repom.postgres.manage import generate_docker_compose

        generator = generate_docker_compose()

        # Assertions
        assert len(generator.services) == 1  # PostgreSQL 
        assert generator.services[0].name == "postgres"
        assert generator.services[0].image == "postgres:16-alpine"
        assert generator.services[0].container_name == "repom_postgres"
        assert generator.services[0].depends_on is None  # 


class TestGenerateDockerComposePgAdminEnabled:
    """generate_docker_compose() - pgAdmin """

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_postgres_and_pgadmin_service_generation(self, mock_get_init_dir, mock_config):
        """PostgreSQL  pgAdmin """
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
        mock_pgadmin_container.enabled = True  # 
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

        # pgAdmin  depends_on 
        pgadmin_service = generator.services[1]
        assert pgadmin_service.depends_on is not None
        assert "postgres" in pgadmin_service.depends_on
        assert pgadmin_service.depends_on["postgres"]["condition"] == "service_healthy"

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_pgadmin_yaml_generation(self, mock_get_init_dir, mock_config):
        """pgAdmin  YAML """
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

        # YAML 
        assert "  pgadmin:" in yaml_content
        assert "    image: dpage/pgadmin4:latest" in yaml_content
        assert "    container_name: repom_pgadmin" in yaml_content
        assert "      PGADMIN_DEFAULT_EMAIL: admin@localhost" in yaml_content
        assert "      PGADMIN_DEFAULT_PASSWORD: admin" in yaml_content
        assert "      - \"5050:80\"" in yaml_content
        assert "    depends_on:" in yaml_content
        assert "      postgres:" in yaml_content


class TestGenerateInitSql:
    """generate_init_sql() - DB """

    @patch('repom.postgres.manage.config')
    def test_default_database_names(self, mock_config):
        """ DB epom, repom_dev, repom_test"""
        mock_config.data_path = DATA_PATH
        mock_config.db_name = "repom"  # db_name 
        mock_config.postgres.user = "repom"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        #  CREATE DATABASE gexec
        assert "'CREATE DATABASE \"repom\"'" in sql
        assert "'CREATE DATABASE \"repom_dev\"'" in sql
        assert "'CREATE DATABASE \"repom_test\"'" in sql
        # IF NOT EXISTS 
        assert "WHERE NOT EXISTS" in sql
        assert "pg_database" in sql
        # GRANT  DB 
        assert 'GRANT ALL PRIVILEGES ON DATABASE "repom" TO "repom";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "repom_dev" TO "repom";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "repom_test" TO "repom";' in sql

    @patch('repom.postgres.manage.config')
    def test_custom_database_names(self, mock_config):
        """ DB ine_py, mine_py_dev, mine_py_test"""
        mock_config.data_path = DATA_PATH
        mock_config.db_name = "mine_py"  # db_name 
        mock_config.postgres.user = "mine_py"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        #  CREATE DATABASE gexec
        assert "'CREATE DATABASE \"mine_py\"'" in sql
        assert "'CREATE DATABASE \"mine_py_dev\"'" in sql
        assert "'CREATE DATABASE \"mine_py_test\"'" in sql
        # GRANT  DB 
        assert 'GRANT ALL PRIVILEGES ON DATABASE "mine_py" TO "mine_py";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "mine_py_dev" TO "mine_py";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "mine_py_test" TO "mine_py";' in sql

    @patch('repom.postgres.manage.config')
    def test_environment_prefixing_in_sql(self, mock_config):
        """"""
        mock_config.data_path = DATA_PATH
        mock_config.db_name = "project"  # db_name 
        mock_config.postgres.user = "user"

        from repom.postgres.manage import generate_init_sql

        sql = generate_init_sql()

        #  CREATE DATABASE gexec
        assert "'CREATE DATABASE \"project\"'" in sql
        assert "'CREATE DATABASE \"project_dev\"'" in sql
        assert "'CREATE DATABASE \"project_test\"'" in sql

        #  GRANT 
        assert 'GRANT ALL PRIVILEGES ON DATABASE "project" TO "user";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "project_dev" TO "user";' in sql
        assert 'GRANT ALL PRIVILEGES ON DATABASE "project_test" TO "user";' in sql

    @patch('repom.postgres.manage.config')
    def test_hostile_database_and_user_names_are_quoted(self, mock_config):
        """Identifiers and literals are quoted in generated init SQL."""
        mock_config.data_path = DATA_PATH
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
    """Compose """

    @patch('repom.postgres.manage.config')
    @patch('repom.postgres.manage.PostgresManager.get_compose_dir')
    @patch('repom.postgres.manage.PostgresManager.get_init_dir')
    def test_yaml_file_is_valid(self, mock_get_init_dir, mock_get_compose_dir, mock_config, tmp_path):
        """YAML """
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

        # YAML 
        assert "version: '3.8'" in yaml_content
        assert "services:" in yaml_content
        assert "volumes:" in yaml_content
        assert "  postgres:" in yaml_content
        assert "  repom_postgres_data:" in yaml_content

        # 
        assert "POSTGRES_USER: repom" in yaml_content
        assert "POSTGRES_PASSWORD: repom_dev" in yaml_content
        # Note: POSTGRES_DB DB init 
        assert "POSTGRES_DB" not in yaml_content

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
        mock_pg_config.container = mock_pg_container

        mock_pgadmin_container = MagicMock()
        mock_pgadmin_container.enabled = True
        mock_pgadmin_container.get_container_name.return_value = "repom_pgadmin"
        mock_pgadmin_container.get_volume_name.return_value = "repom_pgadmin_data"
        mock_pgadmin_container.image = "dpage/pgadmin4:latest"
        mock_pgadmin_container.host_port = 5050
        mock_pgadmin_config = MagicMock()
        mock_pgadmin_config.email = "admin@example.com"
        mock_pgadmin_config.password = "pgadmin-secret"
        mock_pgadmin_config.container = mock_pgadmin_container

        mock_config.db_name = "repom"
        mock_config.postgres = mock_pg_config
        mock_config.pgadmin = mock_pgadmin_config
        mock_config.data_path = DATA_PATH

        from repom.postgres.manage import generate

        generate()

        captured = capsys.readouterr()
        assert "postgres-secret" not in captured.out
        assert "pgadmin-secret" not in captured.out


class TestPgAdminServersJson:
    """pgAdmin servers.json """

    @patch('repom.postgres.manage.config')
    def test_generate_pgadmin_servers_json(self, mock_config):
        """servers.json - """
        # Mock setup
        mock_config.data_path = DATA_PATH
        mock_config.postgres.user = "repom"
        mock_config.postgres.password = "repom_dev"
        mock_config.db_name = "repom"  # db_name 
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
        assert server["MaintenanceDB"] == "repom_dev"  # 

    @patch('repom.postgres.manage.config')
    def test_generate_pgadmin_servers_json_custom_config(self, mock_config):
        """servers.json - ONFIG_HOOK """
        # Mock setup -  CONFIG_HOOK 
        mock_config.data_path = DATA_PATH
        mock_config.postgres.user = "mine_py"
        mock_config.postgres.password = "mine_py_dev"
        mock_config.db_name = "mine_py"  # db_name 
        mock_config.postgres.container.get_container_name.return_value = "mine_py_postgres"

        from repom.postgres.manage import generate_pgadmin_servers_json

        # Test
        config_dict = generate_pgadmin_servers_json()

        # Assertions
        server = config_dict["Servers"]["1"]
        assert server["Name"] == "mine_py_postgres"  # 
        assert server["Host"] == "postgres"  # Docker network  "postgres"
        assert server["Username"] == "mine_py"
        assert server["MaintenanceDB"] == "mine_py_dev"  #  DB 


class TestDirectorySeparation:
    """Tests for separate project directory structure (Issue #043)"""

    def test_get_compose_dir_uses_postgres_subdir(self):
        """get_compose_dir postgres """
        from repom.postgres.manage import PostgresManager

        compose_dir = PostgresManager().get_compose_dir()

        # Should be config.data_path/postgres/
        assert str(compose_dir).endswith("postgres")
        assert "postgres" in str(compose_dir)

    def test_postgres_generate_creates_in_postgres_subdir(self):
        """postgres_generate data/repom/postgres/  docker-compose.yml """
        from repom.postgres.manage import PostgresManager, generate

        # Generate files
        generate()

        # Verify files are in postgres subdirectory
        compose_file = PostgresManager().get_compose_dir() / "docker-compose.generated.yml"
        assert compose_file.exists()
        assert "postgres" in str(compose_file.parent)

    def test_postgres_redis_no_conflict(self):
        """postgres_generate  redis_generate """
        from repom.postgres.manage import PostgresManager, generate as postgres_generate
        from repom.redis.manage import RedisManager, generate as redis_generate

        # Generate both
        postgres_generate()
        redis_generate()

        # Verify both files exist in their respective directories
        postgres_compose = PostgresManager().get_compose_dir() / "docker-compose.generated.yml"
        redis_compose = RedisManager().get_compose_dir() / "docker-compose.generated.yml"

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

    def test_module_level_directory_helpers_are_removed(self):
        """module-level get_compose_dir/get_init_dir are no longer public."""
        import pytest

        with pytest.raises(ImportError):
            from repom.postgres.manage import get_compose_dir  # noqa: F401

        with pytest.raises(ImportError):
            from repom.postgres.manage import get_init_dir  # noqa: F401


class TestPostgresEnsureRunning:
    """ensure_running() """

    def _patch_config(self, *, pgadmin_enabled: bool):
        """`repom.postgres.manage.config`  MagicMock """
        mock_config = MagicMock()
        mock_config.postgres.container.get_container_name.return_value = "repom_postgres"
        mock_config.pgadmin.container.enabled = pgadmin_enabled
        mock_config.pgadmin.container.get_container_name.return_value = "repom_pgadmin"
        return mock_config

    def test_returns_when_postgres_and_pgadmin_running(self):
        """postgres  pgAdmin """
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
        """pgAdmin postgres """
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

    def test_starts_when_postgres_down(self):
        """postgres generate + manager.start(timeout) """
        from repom.postgres import manage

        manager_instance = MagicMock()
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

    def test_starts_when_only_pgadmin_down(self):
        """postgres  up pgAdmin down """
        from repom.postgres import manage

        manager_instance = MagicMock()

        def is_container_running(name):
            return name == "repom_postgres"  # pgadmin  False

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
        """include_pgadmin=False pgAdmin """
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

    def test_raises_runtime_error_when_docker_missing(self):
        """docker  RuntimeError """
        import pytest

        from repom.postgres import manage

        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=False)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                side_effect=FileNotFoundError("docker not found"),
            ):
                with pytest.raises(RuntimeError, match="docker command not found"):
                    manage.ensure_running()

    def test_raises_runtime_error_on_timeout(self):
        """manager.start()  TimeoutError  RuntimeError """
        import pytest

        from repom.postgres import manage

        manager_instance = MagicMock()
        manager_instance.start.side_effect = TimeoutError(
            "PostgreSQL did not start within 30 seconds"
        )
        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=False)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate"):
                    with patch.object(
                        manage, "PostgresManager", return_value=manager_instance
                    ):
                        with pytest.raises(RuntimeError, match="Failed to start PostgreSQL"):
                            manage.ensure_running()

    def test_raises_runtime_error_on_system_exit(self):
        """manager.start()  SystemExit RuntimeError """
        import pytest

        from repom.postgres import manage

        manager_instance = MagicMock()
        manager_instance.start.side_effect = SystemExit(1)
        with patch.object(manage, "config", self._patch_config(pgadmin_enabled=False)):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate"):
                    with patch.object(
                        manage, "PostgresManager", return_value=manager_instance
                    ):
                        with pytest.raises(RuntimeError, match="Failed to start PostgreSQL"):
                            manage.ensure_running()



