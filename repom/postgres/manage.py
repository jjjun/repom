"""PostgreSQL Docker 


    uv run postgres_generate  # docker-compose.yml 
    uv run postgres_start      # PostgreSQL 
    uv run postgres_stop       # PostgreSQL 
"""

import subprocess
import sys
import json

from repom.config import config
from basekit.docker_compose import DockerComposeGenerator, DockerService, DockerVolume
from basekit import docker_manager as dm


class PostgresManager(dm.DockerManager):
    """PostgreSQL ocker Manager 

    docker-compose  start/stop/remove  DockerManager 
    """

    SERVICE_NAME = "postgres"
    INIT_SUBDIR = "postgresql_init"
    GENERATE_COMMAND = "postgres_generate"

    def __init__(self):
        super().__init__(data_path=config.data_path)
        self.config = config

    def get_container_name(self) -> str:
        """PostgreSQL """
        return self.config.postgres.container.get_container_name()

    def wait_for_service(self, max_retries: int = 30) -> None:
        """PostgreSQL g_isready """
        container_name = self.get_container_name()
        user = self.config.postgres.user

        def check_postgres_ready():
            try:
                result = subprocess.run(
                    ["docker", "exec", container_name, "pg_isready", "-U", user],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False
                )
                return result.returncode == 0
            except Exception:
                return False

        dm.DockerCommandExecutor.wait_for_readiness(
            check_postgres_ready,
            max_retries=max_retries,
            service_name="PostgreSQL"
        )

    def print_connection_info(self) -> None:
        """PostgreSQL """
        print()
        print(" PostgreSQL Connection:")
        print("  Host: localhost")
        print(f"  Port: {self.config.postgres.container.host_port}")
        print(f"  User: {self.config.postgres.user}")
        print(f"  Password: {self.config.postgres.password}")
        db_name = self.config.db_name
        print(f"  Databases: {db_name}, {db_name}_dev, {db_name}_test")

        # pgAdmin 
        if self.config.pgadmin.container.enabled:
            print()
            print(" pgAdmin Access:")
            print(f"  URL: http://localhost:{self.config.pgadmin.container.host_port}")
            print(f"  Email: {self.config.pgadmin.email}")
            print(f"  Password: {self.config.pgadmin.password}")
            print()
            print("  PostgreSQL server auto-registered (servers.json)")
            print(f"  Server: {self.config.postgres.container.get_container_name()}")


def generate_pgadmin_servers_json() -> dict:
    """pgAdmin 

    config 
    CONFIG_HOOK 

    Returns:
        pgAdmin servers.json ict
    """
    db_dev = f"{config.db_name}_dev"

    return {
        "Servers": {
            "1": {
                "Name": config.postgres.container.get_container_name(),
                "Group": "Servers",
                "Host": "postgres",  # Docker network  URL
                "Port": 5432,
                "Username": config.postgres.user,
                "SSLMode": "prefer",
                "MaintenanceDB": db_dev
            }
        }
    }


def generate_docker_compose() -> DockerComposeGenerator:
    """config  docker-compose.yml """
    manager = PostgresManager()
    pg = config.postgres
    container = pg.container

    # init
    init_dir = manager.get_init_dir()

    # PostgreSQL 
    # Note: POSTGRES_DB OSTGRES_USER DB
    # DB (dev/test/prod)  init 
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
            "start_period": "30s",  # 
        }
    )

    # Docker Volume 
    data_volume = DockerVolume(name=container.get_volume_name())

    # 
    generator = DockerComposeGenerator()
    generator.add_service(postgres_service)
    generator.add_volume(data_volume)

    # pgAdmin 
    if config.pgadmin.container.enabled:
        pgadmin_container = config.pgadmin.container
        # servers.json
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
                    "condition": "service_healthy"
                }
            }
        )
        pgadmin_volume = DockerVolume(name=pgadmin_container.get_volume_name())
        generator.add_service(pgadmin_service)
        generator.add_volume(pgadmin_volume)

    return generator


def generate_init_sql() -> str:
    """ DB 

    config.db_name 
     repom repom, repom_dev, repom_test 

    Note:
        POSTGRES_USER  DB  Docker 
        \\gexec 
        \\gexec  psql ELECT SQL 
    """
    base = config.db_name
    user = config.postgres.user

    return f"""-- {base} project databases
-- Use \\gexec pattern to handle "IF NOT EXISTS" (PostgreSQL doesn't have CREATE DATABASE IF NOT EXISTS)

SELECT 'CREATE DATABASE {base}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{base}')\\gexec
SELECT 'CREATE DATABASE {base}_dev' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{base}_dev')\\gexec
SELECT 'CREATE DATABASE {base}_test' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{base}_test')\\gexec

GRANT ALL PRIVILEGES ON DATABASE {base} TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_dev TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_test TO {user};
"""


def generate():
    """docker-compose.yml """
    manager = PostgresManager()
    #
    init_dir = manager.get_init_dir()
    init_sql = generate_init_sql()
    (init_dir / "01_init_databases.sql").write_text(init_sql, encoding="utf-8")

    # docker-compose.yml
    generator = generate_docker_compose()
    compose_dir = manager.get_compose_dir()
    output_path = compose_dir / "docker-compose.generated.yml"
    generator.write_to_file(output_path)

    # pgAdmin servers.json 
    if config.pgadmin.container.enabled:
        servers_json_path = compose_dir / "servers.json"
        servers_config = generate_pgadmin_servers_json()
        servers_json_path.write_text(json.dumps(servers_config, indent=2), encoding="utf-8")
        print(f"pgAdmin servers config: {servers_json_path}")

    print(f"Generated: {output_path}")
    print(f"   Init SQL: {init_dir / '01_init_databases.sql'}")
    print("\n PostgreSQL Service:")
    print(f"   Container: {config.postgres.container.get_container_name()}")
    print(f"   Port: {config.postgres.container.host_port}")
    print(f"   Volume: {config.postgres.container.get_volume_name()}")

    # pgAdmin 
    if config.pgadmin.container.enabled:
        print("\n pgAdmin Service:")
        print(f"   Container: {config.pgadmin.container.get_container_name()}")
        print(f"   Port: {config.pgadmin.container.host_port}")
        print(f"   Email: {config.pgadmin.email}")
        print(f"   Volume: {config.pgadmin.container.get_volume_name()}")
    else:
        print("\n pgAdmin: Disabled (set config.pgadmin.container.enabled=True to enable)")


def start():
    """PostgreSQL """
    # docker-compose.yml 
    generate()

    manager = PostgresManager()

    try:
        manager.start()
        manager.print_connection_info()
    except TimeoutError as e:
        print(f"{e}")
        print(f"Check logs: docker logs {manager.get_container_name()}")
        sys.exit(1)


def stop():
    """PostgreSQL """
    manager = PostgresManager()

    try:
        manager.stop()
    except SystemExit:
        raise


def ensure_running(
    *,
    timeout_seconds: int = 30,
    include_pgadmin: bool = True,
) -> None:
    """PostgreSQL ( enabled  pgAdmin) 

    running 
     docker-compose.yml ostgresManager.start() 

    DB  / fast-domain lifespan 
    :

    - docker  ``RuntimeError`` 
    - readiness check (`wait_for_service`)  ``timeout_seconds``
      ast-domain  lifespan 
    - ``include_pgadmin``  pgAdmin 
      (CLI  True  OKast-domain True)

    Args:
        timeout_seconds: readiness check  (30)
            ``PostgresManager.start(timeout_seconds=...)`` 
        include_pgadmin: pgAdmin (``config.pgadmin.container.enabled`` 
            True  (True)

    Raises:
        RuntimeError: docker eadiness 
             compose up 
    """
    from basekit.docker_manager import DockerCommandExecutor

    postgres_container_name = config.postgres.container.get_container_name()
    pgadmin_enabled = include_pgadmin and bool(
        getattr(config.pgadmin.container, "enabled", False)
    )
    pgadmin_container_name = (
        config.pgadmin.container.get_container_name() if pgadmin_enabled else None
    )

    try:
        postgres_running = DockerCommandExecutor.is_container_running(
            postgres_container_name
        )
        pgadmin_running = (
            DockerCommandExecutor.is_container_running(pgadmin_container_name)
            if pgadmin_enabled
            else True
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "docker command not found. "
            "Please install Docker Desktop: "
            "https://www.docker.com/products/docker-desktop"
        ) from exc

    if postgres_running and pgadmin_running:
        return

    status_parts = [f"postgres={'up' if postgres_running else 'down'}"]
    if pgadmin_enabled:
        status_parts.append(f"pgadmin={'up' if pgadmin_running else 'down'}")
    print(
        f"\n[PostgreSQL] auto-start ({', '.join(status_parts)}); "
        "generating compose and starting containers..."
    )

    try:
        generate()
        manager = PostgresManager()
        manager.start(timeout_seconds=timeout_seconds)
    except (TimeoutError, SystemExit) as exc:
        raise RuntimeError(
            f"Failed to start PostgreSQL via Docker: {exc}"
        ) from exc


def remove():
    """PostgreSQL """
    manager = PostgresManager()

    try:
        manager.remove()
    except SystemExit:
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage.py [generate|start|stop|remove]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "generate":
        generate()
    elif command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "remove":
        remove()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python manage.py [generate|start|stop|remove]")
        sys.exit(1)


