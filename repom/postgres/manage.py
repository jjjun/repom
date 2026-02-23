"""PostgreSQL Docker 環境管理スクリプト

使用方法:
    poetry run postgres_generate  # docker-compose.yml を生成
    poetry run postgres_start      # PostgreSQL を起動
    poetry run postgres_stop       # PostgreSQL を停止
"""

import subprocess
import sys
import json
from pathlib import Path

from repom.config import config
from repom._.docker_compose import DockerComposeGenerator, DockerService, DockerVolume
from repom._ import docker_manager as dm


def get_compose_dir() -> Path:
    """docker-compose.yml の保存先ディレクトリを取得

    Returns:
        config.data_path/postgres/ ディレクトリ（分離プロジェクト構造）
    """
    compose_dir = Path(config.data_path) / "postgres"
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir


class PostgresManager(dm.DockerManager):
    """PostgreSQL コンテナの管理（Docker Manager 基盤を使用）

    docker-compose による start/stop/remove は DockerManager 基盤クラスから継承
    """

    def __init__(self):
        self.config = config

    def get_container_name(self) -> str:
        """PostgreSQL コンテナ名を返す"""
        return self.config.postgres.container.get_container_name()

    def get_compose_file_path(self) -> Path:
        """compose ファイルのパスを返す"""
        compose_file = get_compose_dir() / "docker-compose.generated.yml"
        if not compose_file.exists():
            raise FileNotFoundError(
                f"Compose file not found: {compose_file}\n"
                f"Hint: Run 'poetry run postgres_generate' first"
            )
        return compose_file

    def wait_for_service(self, max_retries: int = 30) -> None:
        """PostgreSQL の起動を待機（pg_isready による確認）"""
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
        """PostgreSQL 接続情報を表示"""
        print()
        print("📦 PostgreSQL Connection:")
        print(f"  Host: localhost")
        print(f"  Port: {self.config.postgres.container.host_port}")
        print(f"  User: {self.config.postgres.user}")
        print(f"  Password: {self.config.postgres.password}")
        print(f"  Databases: repom_dev, repom_test, repom_prod")

        # pgAdmin 情報を出力（有効な場合のみ）
        if self.config.pgadmin.container.enabled:
            print()
            print("🎨 pgAdmin Access:")
            print(f"  URL: http://localhost:{self.config.pgadmin.container.host_port}")
            print(f"  Email: {self.config.pgadmin.email}")
            print(f"  Password: {self.config.pgadmin.password}")
            print()
            print("  ✅ PostgreSQL server auto-registered (servers.json)")
            print(f"  Server: {self.config.postgres.container.get_container_name()}")


def get_init_dir() -> Path:
    """PostgreSQL 初期化スクリプトのディレクトリを取得

    Returns:
        config.data_path/postgresql_init/ ディレクトリ
    """
    compose_dir = get_compose_dir()
    init_dir = compose_dir / "postgresql_init"
    init_dir.mkdir(parents=True, exist_ok=True)
    return init_dir


def generate_pgadmin_servers_json() -> dict:
    """pgAdmin サーバー設定ファイルの内容を生成

    config の値を使用して動的に生成します。
    CONFIG_HOOK でカスタマイズされた値が反映されます。

    Returns:
        pgAdmin servers.json の内容（dict）
    """
    base_db = config.postgres.database or "repom"
    db_dev = f"{base_db}_dev"

    return {
        "Servers": {
            "1": {
                "Name": config.postgres.container.get_container_name(),
                "Group": "Servers",
                "Host": "postgres",  # Docker network 内での URL
                "Port": 5432,
                "Username": config.postgres.user,
                "SSLMode": "prefer",
                "MaintenanceDB": db_dev
            }
        }
    }


def generate_docker_compose() -> DockerComposeGenerator:
    """config から docker-compose.yml 生成器を作成"""
    pg = config.postgres
    container = pg.container

    # init スクリプトのパスを取得
    init_dir = get_init_dir()

    # PostgreSQL サービスを定義
    # Note: POSTGRES_DB は省略（POSTGRES_USER と同名のDBが自動作成される）
    # 実際の環境別DB (dev/test/prod) は init スクリプトで作成
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
        }
    )

    # Docker Volume を定義
    data_volume = DockerVolume(name=container.get_volume_name())

    # 生成器を作成
    generator = DockerComposeGenerator()
    generator.add_service(postgres_service)
    generator.add_volume(data_volume)

    # pgAdmin サービスをオプショナルに追加
    if config.pgadmin.container.enabled:
        pgadmin_container = config.pgadmin.container
        # servers.json のパスを作成
        servers_json_path = get_compose_dir() / "servers.json"

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
    """環境別の DB 作成スクリプトを生成

    config.postgres.database でカスタマイズ可能（環境プレフィックスなしのベース名）
    デフォルト: repom → repom_dev, repom_test, repom_prod を作成
    """
    # ベース名を取得（環境プレフィックスなし）
    base = config.postgres.database or "repom"
    user = config.postgres.user

    return f"""-- {base} project databases
CREATE DATABASE {base}_dev;
CREATE DATABASE {base}_test;
CREATE DATABASE {base}_prod;

GRANT ALL PRIVILEGES ON DATABASE {base}_dev TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_test TO {user};
GRANT ALL PRIVILEGES ON DATABASE {base}_prod TO {user};
"""


def generate():
    """docker-compose.yml を生成（コマンドから呼び出し可能）"""
    # 初期化スクリプトを生成
    init_dir = get_init_dir()
    init_sql = generate_init_sql()
    (init_dir / "01_init_databases.sql").write_text(init_sql, encoding="utf-8")

    # docker-compose.yml を生成
    generator = generate_docker_compose()
    compose_dir = get_compose_dir()
    output_path = compose_dir / "docker-compose.generated.yml"
    generator.write_to_file(output_path)

    # pgAdmin servers.json を生成（有効な場合のみ）
    if config.pgadmin.container.enabled:
        servers_json_path = compose_dir / "servers.json"
        servers_config = generate_pgadmin_servers_json()
        servers_json_path.write_text(json.dumps(servers_config, indent=2), encoding="utf-8")
        print(f"✅ pgAdmin servers config: {servers_json_path}")

    print(f"✅ Generated: {output_path}")
    print(f"   Init SQL: {init_dir / '01_init_databases.sql'}")
    print(f"\n📦 PostgreSQL Service:")
    print(f"   Container: {config.postgres.container.get_container_name()}")
    print(f"   Port: {config.postgres.container.host_port}")
    print(f"   Volume: {config.postgres.container.get_volume_name()}")

    # pgAdmin 情報を出力（有効な場合のみ）
    if config.pgadmin.container.enabled:
        print(f"\n🎨 pgAdmin Service:")
        print(f"   Container: {config.pgadmin.container.get_container_name()}")
        print(f"   Port: {config.pgadmin.container.host_port}")
        print(f"   Email: {config.pgadmin.email}")
        print(f"   Volume: {config.pgadmin.container.get_volume_name()}")
    else:
        print(f"\n⚪ pgAdmin: Disabled (set config.pgadmin.container.enabled=True to enable)")


def start():
    """PostgreSQL を起動"""
    # docker-compose.yml を生成
    generate()

    manager = PostgresManager()

    try:
        manager.start()
        manager.print_connection_info()
    except TimeoutError as e:
        print(f"❌ {e}")
        print(f"Check logs: docker logs {manager.get_container_name()}")
        sys.exit(1)


def stop():
    """PostgreSQL を停止（コンテナ停止のみ、削除はしない）"""
    manager = PostgresManager()

    try:
        manager.stop()
    except SystemExit:
        raise


def remove():
    """PostgreSQL コンテナとボリュームを削除（完全リセット）"""
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
