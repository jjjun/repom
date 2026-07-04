"""PostgreSQL container management commands.

Console scripts:
    uv run postgres_generate
    uv run postgres_start
    uv run postgres_stop
    uv run postgres_remove
"""

from __future__ import annotations

import json
import subprocess

from repom.config import config
from repom.postgres.credentials import mask_secret, quote_identifier, quote_literal
from basekit.docker_compose import (
    DockerComposeGenerator,
    DockerService,
    DockerVolume,
)
from basekit.docker_manager import DockerCommandExecutor, DockerManager
from repom.docker_service import (
    ensure_running as ensure_container_service_running,
    remove_service,
    start_service,
    stop_service,
)

COMPOSE_FILENAME = "docker-compose.generated.yml"


class PostgresManager(DockerManager):
    """Container manager for the repom PostgreSQL service."""

    SERVICE_NAME = "postgres"
    INIT_SUBDIR = "postgresql_init"
    GENERATE_COMMAND = "postgres_generate"

    def __init__(self):
        super().__init__(data_path=config.data_path)
        self.config = config

    def get_container_name(self) -> str:
        """Return the configured PostgreSQL container name."""

        return self.config.postgres.container.get_container_name()

    def wait_for_service(self, max_retries: int = 30) -> None:
        """Wait until the PostgreSQL readiness command succeeds in the container."""

        container_name = self.get_container_name()
        user = self.config.postgres.user

        def check_postgres_ready():
            try:
                result = subprocess.run(
                    ["docker", "exec", container_name, "pg_isready", "-U", user],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                return result.returncode == 0
            except Exception:
                return False

        DockerCommandExecutor.wait_for_readiness(
            check_postgres_ready,
            max_retries=max_retries,
            service_name="PostgreSQL",
        )

    def print_connection_info(self) -> None:
        """Print local PostgreSQL and pgAdmin connection details."""

        print()
        print(" PostgreSQL Connection:")
        print("  Host: localhost")
        print(f"  Port: {self.config.postgres.container.host_port}")
        print(f"  User: {self.config.postgres.user}")
        postgres_password = mask_secret(
            self.config.postgres.password,
            (self.config.postgres.password,),
        )
        print(f"  Password: {postgres_password}")
        db_name = self.config.db_name
        print(f"  Databases: {db_name}, {db_name}_dev, {db_name}_test")

        if self.config.pgadmin.container.enabled:
            print()
            print(" pgAdmin Access:")
            print(f"  URL: http://localhost:{self.config.pgadmin.container.host_port}")
            print(f"  Email: {self.config.pgadmin.email}")
            pgadmin_password = mask_secret(
                self.config.pgadmin.password,
                (self.config.pgadmin.password,),
            )
            print(f"  Password: {pgadmin_password}")
            print()
            print("  PostgreSQL server auto-registered (servers.json)")
            print(f"  Server: {self.config.postgres.container.get_container_name()}")


def generate_pgadmin_servers_json() -> dict:
    """Build the pgAdmin servers.json structure from the active config."""

    db_dev = f"{config.db_name}_dev"

    return {
        "Servers": {
            "1": {
                "Name": config.postgres.container.get_container_name(),
                "Group": "Servers",
                "Host": "postgres",
                "Port": 5432,
                "Username": config.postgres.user,
                "SSLMode": "prefer",
                "MaintenanceDB": db_dev,
            }
        }
    }


def generate_docker_compose() -> DockerComposeGenerator:
    """Generate a compose model for PostgreSQL and optional pgAdmin."""

    manager = PostgresManager()
    pg = config.postgres
    container = pg.container
    init_dir = manager.get_init_dir()

    postgres_service = DockerService(
        name="postgres",
        image=container.image,
        container_name=container.get_container_name(),
        environment={
            "POSTGRES_USER": pg.user,
            "POSTGRES_PASSWORD": pg.password,
        },
        ports=[f"{container.host_port}:5432"],
        volumes=[
            f"{container.get_volume_name()}:/var/lib/postgresql/data",
            f"{init_dir.absolute()}:/docker-entrypoint-initdb.d",
        ],
        healthcheck={
            "test": f'["CMD-SHELL", "pg_isready -U {pg.user}"]',
            "interval": "5s",
            "timeout": "5s",
            "retries": 5,
            "start_period": "30s",
        },
    )

    generator = DockerComposeGenerator()
    generator.add_service(postgres_service)
    generator.add_volume(DockerVolume(name=container.get_volume_name()))

    if config.pgadmin.container.enabled:
        pgadmin_container = config.pgadmin.container
        servers_json_path = manager.get_compose_dir() / "servers.json"

        pgadmin_service = DockerService(
            name="pgadmin",
            image=pgadmin_container.image,
            container_name=pgadmin_container.get_container_name(),
            environment={
                "PGADMIN_DEFAULT_EMAIL": config.pgadmin.email,
                "PGADMIN_DEFAULT_PASSWORD": config.pgadmin.password,
            },
            ports=[f"{pgadmin_container.host_port}:80"],
            volumes=[
                f"{pgadmin_container.get_volume_name()}:/var/lib/pgadmin",
                f"{servers_json_path}:/pgadmin4/servers.json",
            ],
            depends_on={
                "postgres": {
                    "condition": "service_healthy",
                }
            },
        )
        generator.add_service(pgadmin_service)
        generator.add_volume(DockerVolume(name=pgadmin_container.get_volume_name()))

    return generator


def generate_init_sql() -> str:
    """Generate SQL that creates the project PostgreSQL databases."""

    base = config.db_name
    user = config.postgres.user
    databases = (base, f"{base}_dev", f"{base}_test")
    create_lines = []
    grant_lines = []
    quoted_user = quote_identifier(user)
    for database in databases:
        create_database_sql = f"CREATE DATABASE {quote_identifier(database)}"
        create_lines.append(
            "SELECT "
            f"{quote_literal(create_database_sql)} "
            "WHERE NOT EXISTS "
            f"(SELECT FROM pg_database WHERE datname = {quote_literal(database)})"
            "\\gexec"
        )
        grant_lines.append(
            "GRANT ALL PRIVILEGES ON DATABASE "
            f"{quote_identifier(database)} TO {quoted_user};"
        )
    create_sql = "\n".join(create_lines)
    grant_sql = "\n".join(grant_lines)

    return f"""-- Project databases
-- Use \\gexec pattern to handle "IF NOT EXISTS" (PostgreSQL doesn't have CREATE DATABASE IF NOT EXISTS)

{create_sql}

{grant_sql}
"""


def generate():
    """Write PostgreSQL compose and initialization files."""

    manager = PostgresManager()
    init_dir = manager.get_init_dir()
    init_sql = generate_init_sql()
    (init_dir / "01_init_databases.sql").write_text(init_sql, encoding="utf-8")

    generator = generate_docker_compose()
    compose_dir = manager.get_compose_dir()
    output_path = compose_dir / COMPOSE_FILENAME
    generator.write_to_file(output_path)

    if config.pgadmin.container.enabled:
        servers_json_path = compose_dir / "servers.json"
        servers_config = generate_pgadmin_servers_json()
        servers_json_path.write_text(
            json.dumps(servers_config, indent=2),
            encoding="utf-8",
        )
        print(f"pgAdmin servers config: {servers_json_path}")

    print(f"Generated: {output_path}")
    print(f"   Init SQL: {init_dir / '01_init_databases.sql'}")
    print("\n PostgreSQL Service:")
    print(f"   Container: {config.postgres.container.get_container_name()}")
    print(f"   Port: {config.postgres.container.host_port}")
    print(f"   Volume: {config.postgres.container.get_volume_name()}")

    if config.pgadmin.container.enabled:
        print("\n pgAdmin Service:")
        print(f"   Container: {config.pgadmin.container.get_container_name()}")
        print(f"   Port: {config.pgadmin.container.host_port}")
        print(f"   Email: {config.pgadmin.email}")
        print(f"   Volume: {config.pgadmin.container.get_volume_name()}")
    else:
        print("\n pgAdmin: Disabled (set config.pgadmin.container.enabled=True to enable)")


def start():
    """Generate files and start PostgreSQL."""

    start_service(PostgresManager, generate)


def stop():
    """Stop PostgreSQL."""

    stop_service(PostgresManager)


def ensure_running(
    *,
    timeout_seconds: int = 30,
    include_pgadmin: bool = True,
) -> None:
    """Ensure PostgreSQL, and optionally pgAdmin, are running.

    This helper is intended for application lifespan hooks. It generates the
    compose files and starts containers when any required container is down.

    Args:
        timeout_seconds: Number of seconds to wait for readiness.
        include_pgadmin: Include pgAdmin in the running-container check when
            the pgAdmin container is enabled in config.

    Raises:
        RuntimeError: The container runtime is unavailable or startup fails.
    """

    container_names = {
        "postgres": config.postgres.container.get_container_name(),
    }
    if include_pgadmin and bool(getattr(config.pgadmin.container, "enabled", False)):
        container_names["pgadmin"] = config.pgadmin.container.get_container_name()

    ensure_container_service_running(
        PostgresManager,
        container_names,
        generate,
        "PostgreSQL",
        timeout_seconds,
    )


def remove():
    """Remove PostgreSQL containers and volumes."""

    remove_service(PostgresManager)
