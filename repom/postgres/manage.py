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
from pathlib import Path

from repom.config import config
from repom.credentials import DEFAULT_CREDENTIAL_PLACEHOLDER, reject_default_credential
from repom.docker_compose_safety import (
    format_bound_port,
    format_env_file,
    quote_yaml_string,
    reject_control_characters,
    validate_stored_secret_values,
    validate_secret_file_overwrite,
    write_secret_file,
)
from repom.postgres.credentials import mask_secret, quote_identifier, quote_literal
from basekit.docker_compose import (
    DockerComposeGenerator,
    DockerService,
    DockerVolume,
)
from basekit.docker_manager import DockerCommandExecutor, DockerManager
from repom.docker_service import (
    _force_regenerate_from_args,
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
        print("  Host: 127.0.0.1")
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
            print(f"  URL: http://127.0.0.1:{self.config.pgadmin.container.host_port}")
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


def generate_docker_compose(
    *, validate_credentials: bool = True
) -> DockerComposeGenerator:
    """Generate a compose model for PostgreSQL and optional pgAdmin."""

    manager = PostgresManager()
    pg = config.postgres
    container = pg.container
    init_dir = manager.get_init_dir()

    user = reject_control_characters(pg.user, field_name="postgres.user")
    if validate_credentials:
        reject_default_credential(pg.password, env_var="POSTGRES_PASSWORD")
        reject_control_characters(pg.password, field_name="postgres.password")
    container_name = reject_control_characters(
        container.get_container_name(), field_name="postgres.container.container_name"
    )
    volume_name = reject_control_characters(
        container.get_volume_name(), field_name="postgres.container.volume_name"
    )

    postgres_service = DockerService(
        name="postgres",
        image=container.image,
        container_name=container_name,
        environment={
            "POSTGRES_USER": quote_yaml_string(user),
            "POSTGRES_PASSWORD": quote_yaml_string("${POSTGRES_PASSWORD}"),
        },
        ports=[
            format_bound_port(container.host_port, 5432, expose_to_lan=container.expose_to_lan)
        ],
        volumes=[
            f"{volume_name}:/var/lib/postgresql/data",
            f"{init_dir.absolute()}:/docker-entrypoint-initdb.d",
        ],
        healthcheck={
            "test": f'["CMD", "pg_isready", "-U", {quote_yaml_string(user)}]',
            "interval": "5s",
            "timeout": "5s",
            "retries": 5,
            "start_period": "30s",
        },
    )

    generator = DockerComposeGenerator()
    generator.add_service(postgres_service)
    generator.add_volume(DockerVolume(name=volume_name))

    if config.pgadmin.container.enabled:
        pgadmin_container = config.pgadmin.container
        pgadmin_email = reject_control_characters(
            config.pgadmin.email, field_name="pgadmin.email"
        )
        if validate_credentials:
            reject_default_credential(
                config.pgadmin.password, env_var="PGADMIN_DEFAULT_PASSWORD"
            )
            reject_control_characters(
                config.pgadmin.password, field_name="pgadmin.password"
            )
        pgadmin_container_name = reject_control_characters(
            pgadmin_container.get_container_name(),
            field_name="pgadmin.container.container_name",
        )
        pgadmin_volume_name = reject_control_characters(
            pgadmin_container.get_volume_name(),
            field_name="pgadmin.container.volume_name",
        )
        servers_json_path = manager.get_compose_dir() / "servers.json"

        pgadmin_service = DockerService(
            name="pgadmin",
            image=pgadmin_container.image,
            container_name=pgadmin_container_name,
            environment={
                "PGADMIN_DEFAULT_EMAIL": quote_yaml_string(pgadmin_email),
                "PGADMIN_DEFAULT_PASSWORD": quote_yaml_string(
                    "${PGADMIN_DEFAULT_PASSWORD}"
                ),
            },
            ports=[
                format_bound_port(
                    pgadmin_container.host_port,
                    80,
                    expose_to_lan=pgadmin_container.expose_to_lan,
                )
            ],
            volumes=[
                f"{pgadmin_volume_name}:/var/lib/pgadmin",
                f"{servers_json_path}:/pgadmin4/servers.json",
            ],
            depends_on={
                "postgres": {
                    "condition": "service_healthy",
                }
            },
        )
        generator.add_service(pgadmin_service)
        generator.add_volume(DockerVolume(name=pgadmin_volume_name))

    return generator


def generate_init_sql() -> str:
    """Generate SQL that creates the project PostgreSQL databases."""

    base = reject_control_characters(config.db_name, field_name="db_name")
    user = reject_control_characters(config.postgres.user, field_name="postgres.user")
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


def generate(*, overwrite_secrets: bool = False):
    """Write PostgreSQL files, refusing changed secrets unless overridden."""

    manager = PostgresManager()
    generator = generate_docker_compose()

    init_dir = manager.get_init_dir()
    init_sql = generate_init_sql()
    init_sql_path = init_dir / "01_init_databases.sql"

    compose_dir = manager.get_compose_dir()
    output_path = compose_dir / COMPOSE_FILENAME

    secrets = {"POSTGRES_PASSWORD": config.postgres.password}
    if config.pgadmin.container.enabled:
        secrets["PGADMIN_DEFAULT_PASSWORD"] = config.pgadmin.password
    env_path = compose_dir / ".env"
    env_content = format_env_file(secrets)
    rotation_commands = ("postgres_rotate_credentials",)
    if config.pgadmin.container.enabled:
        rotation_commands += ("pgadmin_rotate_password",)
    validate_secret_file_overwrite(
        env_path,
        env_content,
        overwrite_secrets=overwrite_secrets,
        rotation_commands=rotation_commands,
    )

    init_sql_path.write_text(init_sql, encoding="utf-8")
    generator.write_to_file(output_path)

    if config.pgadmin.container.enabled:
        servers_json_path = compose_dir / "servers.json"
        servers_config = generate_pgadmin_servers_json()
        servers_json_path.write_text(
            json.dumps(servers_config, indent=2),
            encoding="utf-8",
        )
        print(f"pgAdmin servers config: {servers_json_path}")

    write_secret_file(env_path, env_content)

    print(f"Generated: {output_path}")
    print(f"   Init SQL: {init_sql_path}")
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


def _write_secret_free_artifacts() -> None:
    """Regenerate PostgreSQL artifacts without changing the compose-dir secrets."""

    manager = PostgresManager()
    generator = generate_docker_compose(validate_credentials=False)
    init_sql = generate_init_sql()
    init_dir = manager.get_init_dir()
    compose_dir = manager.get_compose_dir()
    (init_dir / "01_init_databases.sql").write_text(init_sql, encoding="utf-8")
    generator.write_to_file(compose_dir / COMPOSE_FILENAME)
    if config.pgadmin.container.enabled:
        servers_json_path = compose_dir / "servers.json"
        servers_config = generate_pgadmin_servers_json()
        servers_json_path.write_text(
            json.dumps(servers_config, indent=2), encoding="utf-8"
        )


def _prepare_auto_start() -> None:
    """Refresh PostgreSQL artifacts while keeping an existing .env authoritative."""

    compose_dir = PostgresManager().get_compose_dir()
    env_path = compose_dir / ".env"
    if not env_path.is_file():
        generate()
        return

    current_secrets = {"POSTGRES_PASSWORD": config.postgres.password}
    if config.pgadmin.container.enabled:
        current_secrets["PGADMIN_DEFAULT_PASSWORD"] = config.pgadmin.password
    rotation_commands = ("postgres_rotate_credentials",)
    if config.pgadmin.container.enabled:
        rotation_commands += ("pgadmin_rotate_password",)
    validate_stored_secret_values(
        env_path,
        current_secrets,
        default_credential_placeholder=DEFAULT_CREDENTIAL_PLACEHOLDER,
        rotation_commands=rotation_commands,
        generate_command="postgres_generate",
    )
    _write_secret_free_artifacts()


def start(*, overwrite_secrets: bool = False):
    """Generate files and start PostgreSQL."""

    start_service(
        PostgresManager,
        lambda: generate(overwrite_secrets=overwrite_secrets),
    )


def main_generate() -> None:
    """Console entry point for PostgreSQL file generation."""

    force = _force_regenerate_from_args("Generate PostgreSQL compose files.")
    generate(overwrite_secrets=force)


def main_start() -> None:
    """Console entry point for starting PostgreSQL."""

    force = _force_regenerate_from_args("Generate files and start PostgreSQL.")
    start(overwrite_secrets=force)


def stop():
    """Stop PostgreSQL."""

    _write_secret_free_artifacts()
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
    reported_container_names = [
        config.postgres.container.get_container_name(),
    ]
    if config.pgadmin.container.enabled:
        reported_container_names.append(
            config.pgadmin.container.get_container_name()
        )

    def get_generated_files() -> tuple[Path, Path]:
        compose_dir = PostgresManager().get_compose_dir()
        return (
            compose_dir / COMPOSE_FILENAME,
            compose_dir / ".env",
        )

    ensure_container_service_running(
        PostgresManager,
        container_names,
        generate,
        "PostgreSQL",
        timeout_seconds,
        generated_files=get_generated_files,
        prepare_fn=_prepare_auto_start,
        project_name=config.postgres.container.get_container_name(),
        reported_container_names=tuple(reported_container_names),
    )


def remove():
    """Remove PostgreSQL containers and volumes."""

    _write_secret_free_artifacts()
    remove_service(PostgresManager)
