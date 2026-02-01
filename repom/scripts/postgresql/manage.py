"""PostgreSQL Docker 環境管理スクリプト

使用方法:
    poetry run postgres_start  # PostgreSQL を起動
    poetry run postgres_stop   # PostgreSQL を停止
"""

import subprocess
import time
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
COMPOSE_FILE = SCRIPT_DIR / "docker-compose.yml"


def start():
    """PostgreSQL を起動"""
    print("🐳 Starting PostgreSQL container...")
    
    try:
        subprocess.run(
            ["docker-compose", "-f", str(COMPOSE_FILE), "up", "-d"],
            check=True,
            cwd=str(SCRIPT_DIR)
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
        print("  Host: localhost")
        print("  Port: 5432")
        print("  User: repom")
        print("  Password: repom_dev")
        print("  Databases: repom_dev, repom_test, repom_prod")
    except TimeoutError as e:
        print(f"❌ {e}")
        print("Check logs: docker logs repom_postgres")
        sys.exit(1)


def stop():
    """PostgreSQL を停止"""
    print("🛑 Stopping PostgreSQL container...")
    
    try:
        subprocess.run(
            ["docker-compose", "-f", str(COMPOSE_FILE), "down"],
            check=True,
            cwd=str(SCRIPT_DIR)
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
    for i in range(max_retries):
        result = subprocess.run(
            ["docker", "exec", "repom_postgres", "pg_isready", "-U", "repom"],
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
        print("Usage: python manage.py [start|stop]")
        sys.exit(1)
    
    command = sys.argv[1]
    if command == "start":
        start()
    elif command == "stop":
        stop()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python manage.py [start|stop]")
        sys.exit(1)
