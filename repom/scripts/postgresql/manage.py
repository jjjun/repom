"""PostgreSQL Docker 環境管理スクリプト

使用方法:
    poetry run postgres_generate  # docker-compose.yml を生成
    poetry run postgres_start      # PostgreSQL を起動
    poetry run postgres_stop       # PostgreSQL を停止
"""

import subprocess
import time
import sys
from pathlib import Path

from repom.config import config
from repom._.docker_compose import DockerComposeGenerator, DockerService, DockerVolume


def get_compose_dir() -> Path:
    """docker-compose.yml の保存先ディレクトリを取得

    Returns:
        data/{project_name}/ ディレクトリ
        - repom の場合: data/repom/
        - mine_py の場合: data/mine_py/
        - fast_domain の場合: data/fast_domain/
    """
    project_name = config.postgres.container.project_name
    # data_path の親ディレクトリ (data/) を取得して、project_name を追加
    data_root = Path(config.data_path).parent
    compose_dir = data_root / project_name
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir


def get_init_dir() -> Path:
    """PostgreSQL 初期化スクリプトのディレクトリを取得

    Returns:
        data/{project_name}/postgresql_init/ ディレクトリ
    """
    compose_dir = get_compose_dir()
    init_dir = compose_dir / "postgresql_init"
    init_dir.mkdir(parents=True, exist_ok=True)
    return init_dir


def generate_docker_compose() -> DockerComposeGenerator:
    """config から docker-compose.yml 生成器を作成"""
    pg = config.postgres
    container = pg.container

    # 環境別の DB 名を生成
    base_db = container.project_name
    db_dev = f"{base_db}_dev"

    # init スクリプトのパスを取得
    init_dir = get_init_dir()

    # PostgreSQL サービスを定義
    postgres_service = DockerService(
        name="postgres",
        image=container.image,
        container_name=container.get_container_name(),
        environment={
            "POSTGRES_USER": pg.user,
            "POSTGRES_PASSWORD": pg.password,
            "POSTGRES_DB": db_dev,
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

    return generator


def generate_init_sql() -> str:
    """環境別の DB 作成スクリプトを生成"""
    base = config.postgres.container.project_name
    user = config.postgres.user

    return f"""-- {base} project databases
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

    print(f"✅ Generated: {output_path}")
    print(f"   Init SQL: {init_dir / '01_init_databases.sql'}")
    print(f"   Container: {config.postgres.container.get_container_name()}")
    print(f"   Port: {config.postgres.container.host_port}")
    print(f"   Volume: {config.postgres.container.get_volume_name()}")


def start():
    """PostgreSQL を起動"""
    # docker-compose.yml を生成
    generate()

    print()
    print("🐳 Starting PostgreSQL container...")

    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"

    try:
        subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            check=True,
            cwd=str(compose_dir)
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start PostgreSQL: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ docker-compose command not found.")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        sys.exit(1)

    print("⏳ Waiting for PostgreSQL to be ready...")

    try:
        wait_for_postgres()
        print("✅ PostgreSQL is ready")
        print()
        print("Connection info:")
        print(f"  Host: localhost")
        print(f"  Port: {config.postgres.container.host_port}")
        print(f"  User: {config.postgres.user}")
        print(f"  Password: {config.postgres.password}")
        print(f"  Databases: {config.postgres.container.project_name}_dev, {config.postgres.container.project_name}_test, {config.postgres.container.project_name}_prod")
    except TimeoutError as e:
        print(f"❌ {e}")
        print(f"Check logs: docker logs {config.postgres.container.get_container_name()}")
        sys.exit(1)


def stop():
    """PostgreSQL を停止"""
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"

    if not compose_file.exists():
        print("⚠️  docker-compose.generated.yml が見つかりません")
        print(f"   Expected: {compose_file}")
        print()
        print("ヒント: 先に 'poetry run postgres_generate' を実行してください")
        return

    print("🛑 Stopping PostgreSQL container...")

    try:
        subprocess.run(
            ["docker-compose", "-f", str(compose_file), "down"],
            check=True,
            cwd=str(compose_dir)
        )
        print("✅ PostgreSQL stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to stop PostgreSQL: {e}")
        sys.exit(1)


def wait_for_postgres(max_retries=30):
    """PostgreSQL の起動を待機

    Args:
        max_retries: 最大リトライ回数（デフォルト: 30秒）

    Raises:
        TimeoutError: 指定時間内に起動しなかった場合
    """
    container_name = config.postgres.container.get_container_name()
    user = config.postgres.user

    for i in range(max_retries):
        result = subprocess.run(
            ["docker", "exec", container_name, "pg_isready", "-U", user],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return True

        # 進捗を表示
        if (i + 1) % 5 == 0:
            print(f"  Still waiting... ({i + 1}/{max_retries}s)")

        time.sleep(1)

    raise TimeoutError(f"PostgreSQL did not start within {max_retries} seconds")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage.py [generate|start|stop]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "generate":
        generate()
    elif command == "start":
        start()
    elif command == "stop":
        stop()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python manage.py [generate|start|stop]")
        sys.exit(1)
