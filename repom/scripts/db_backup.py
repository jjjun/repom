from repom.config import config
from repom.logging import get_logger
from repom._.docker_manager import DockerCommandExecutor
import os
import shutil
import subprocess
import gzip
from datetime import datetime
from pathlib import Path

# ロガーを取得
logger = get_logger(__name__)

# Maximum number of backups to keep per database name
MAX_BACKUPS_PER_DB = 3


def backup_sqlite():
    """SQLite データベースのバックアップ処理"""
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database file: {config.sqlite.db_file_path}")

    # Ensure backup directory exists
    os.makedirs(config.db_backup_path, exist_ok=True)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Get original db file name and extension
    base_name = os.path.basename(config.sqlite.db_file_path)
    name, ext = os.path.splitext(base_name)
    # Format datetime (no milliseconds)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create backup file name: <name>_<datetime><ext>
    backup_name = f"{name}_{now_str}{ext}"
    backup_path = os.path.join(config.db_backup_path, backup_name)
    logger.debug(f"Backup file name: {backup_name}")

    # Find existing backups for this db name
    existing = [f for f in os.listdir(config.db_backup_path)
                if f.startswith(name + "_") and f.endswith(ext)]
    # Sort by creation time (oldest first)
    existing.sort()
    logger.debug(f"Found {len(existing)} existing backups for {name}")

    if len(existing) >= MAX_BACKUPS_PER_DB:
        # Remove oldest backups to keep only MAX_BACKUPS_PER_DB-1
        to_remove = existing[:len(existing) - MAX_BACKUPS_PER_DB + 1]
        logger.info(f"Removing {len(to_remove)} old backup(s) to maintain limit of {MAX_BACKUPS_PER_DB}")
        for old in to_remove:
            old_path = os.path.join(config.db_backup_path, old)
            os.remove(old_path)
            print(f"Removed old backup: {old}")
            logger.warning(f"Removed old backup: {old}")

    # Copy the file
    logger.debug(f"Copying {config.sqlite.db_file_path} to {backup_path}")
    shutil.copy2(config.sqlite.db_file_path, backup_path)
    print(f"Backup created: {backup_path}")
    logger.info(f"Backup created successfully: {backup_name}")


def backup_postgresql_via_host():
    """PostgreSQL データベースのバックアップ処理（ホスト側 pg_dump 使用）

    フォールバック実装：Docker コンテナが起動していない場合に使用されます。
    ホスト環境に pg_dump がインストールされている必要があります。
    """
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database: {config.postgres_db}")

    # Ensure backup directory exists
    os.makedirs(config.db_backup_path, exist_ok=True)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Create backup file name: db_<datetime>.sql.gz
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"db_{now_str}.sql.gz"
    backup_path = Path(config.db_backup_path) / backup_name
    logger.debug(f"Backup file name: {backup_name}")

    # Find existing backups (db_*.sql.gz)
    existing = sorted([
        f for f in os.listdir(config.db_backup_path)
        if f.startswith("db_") and f.endswith(".sql.gz")
    ])
    logger.debug(f"Found {len(existing)} existing backups")

    if len(existing) >= MAX_BACKUPS_PER_DB:
        # Remove oldest backups to keep only MAX_BACKUPS_PER_DB-1
        to_remove = existing[:len(existing) - MAX_BACKUPS_PER_DB + 1]
        logger.info(f"Removing {len(to_remove)} old backup(s) to maintain limit of {MAX_BACKUPS_PER_DB}")
        for old in to_remove:
            old_path = os.path.join(config.db_backup_path, old)
            os.remove(old_path)
            print(f"Removed old backup: {old}")
            logger.warning(f"Removed old backup: {old}")

    # pg_dump コマンド実行
    try:
        logger.info("Starting pg_dump process")
        env = os.environ.copy()
        env['PGPASSWORD'] = config.postgres.password

        # pg_dump コマンド
        pg_dump_cmd = [
            'pg_dump',
            '-h', config.postgres.host,
            '-p', str(config.postgres.port),
            '-U', config.postgres.user,
            '-d', config.postgres_db,
            '--clean',  # DROP statements を含める
            '--if-exists',  # DROP IF EXISTS で中断防止
            '--no-owner',  # OWNER設定を出力しない
            '--no-acl',  # ACL設定を出力しない
        ]

        logger.debug(f"Executing: {' '.join(pg_dump_cmd)} (PGPASSWORD hidden)")

        # pg_dump 実行 → gzip 圧縮
        pg_dump_proc = subprocess.Popen(
            pg_dump_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # gzip 圧縮
        with gzip.open(backup_path, 'wb') as gz_file:
            for line in pg_dump_proc.stdout:
                gz_file.write(line)

        # pg_dump の終了を待つ
        _, stderr = pg_dump_proc.communicate()

        if pg_dump_proc.returncode != 0:
            error_msg = stderr.decode('utf-8')
            logger.error(f"pg_dump failed: {error_msg}")
            print(f"Error: pg_dump failed\n{error_msg}")
            if backup_path.exists():
                backup_path.unlink()  # 失敗したバックアップファイルを削除
            return

        # バックアップファイルサイズ確認
        file_size = backup_path.stat().st_size
        logger.info(f"Backup file size: {file_size / (1024 * 1024):.2f} MB")

        if file_size == 0:
            logger.error("Backup file is empty")
            print("Error: Backup file is empty")
            backup_path.unlink()
            return

        print(f"Backup created: {backup_path}")
        logger.info(f"Backup created successfully: {backup_name}")

    except FileNotFoundError:
        logger.error("pg_dump command not found. Please install PostgreSQL client tools.")
        print("Error: pg_dump command not found")
        print("Please install PostgreSQL client tools and ensure 'pg_dump' is in your PATH")
        return
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        if backup_path.exists():
            backup_path.unlink()
        return


def backup_postgresql_via_docker():
    """PostgreSQL データベースのバックアップ処理（Docker exec 使用）

    Docker コンテナ内の pg_dump を使用してバックアップを作成します。
    ホスト環境に PostgreSQL クライアントツールのインストールは不要です。
    """
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database: {config.postgres_db}")

    container_name = config.postgres.container.get_container_name()
    logger.info(f"Using Docker container: {container_name}")

    # Ensure backup directory exists
    os.makedirs(config.db_backup_path, exist_ok=True)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Create backup file name: db_<datetime>.sql.gz
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"db_{now_str}.sql.gz"
    backup_path = Path(config.db_backup_path) / backup_name
    logger.debug(f"Backup file name: {backup_name}")

    # Find existing backups (db_*.sql.gz)
    existing = sorted([
        f for f in os.listdir(config.db_backup_path)
        if f.startswith("db_") and f.endswith(".sql.gz")
    ])
    logger.debug(f"Found {len(existing)} existing backups")

    if len(existing) >= MAX_BACKUPS_PER_DB:
        # Remove oldest backups to keep only MAX_BACKUPS_PER_DB-1
        to_remove = existing[:len(existing) - MAX_BACKUPS_PER_DB + 1]
        logger.info(f"Removing {len(to_remove)} old backup(s) to maintain limit of {MAX_BACKUPS_PER_DB}")
        for old in to_remove:
            old_path = os.path.join(config.db_backup_path, old)
            os.remove(old_path)
            print(f"Removed old backup: {old}")
            logger.warning(f"Removed old backup: {old}")

    # docker exec で pg_dump 実行
    try:
        logger.info("Starting pg_dump via Docker exec")

        # pg_dump コマンド構築
        pg_dump_cmd = [
            "pg_dump",
            "-U", config.postgres.user,
            "-d", config.postgres_db,
            "--clean",      # DROP statements を含める
            "--if-exists",  # DROP IF EXISTS で中断防止
            "--no-owner",   # OWNER設定を出力しない
            "--no-acl",     # ACL設定を出力しない
        ]

        logger.debug(f"Executing: docker exec {container_name} {' '.join(pg_dump_cmd)}")

        # docker exec で pg_dump 実行
        result = DockerCommandExecutor.exec_command(
            container_name=container_name,
            command=pg_dump_cmd,
            capture_output=True
        )

        # gzip 圧縮して保存
        with gzip.open(backup_path, 'wb') as gz_file:
            gz_file.write(result.stdout)

        # バックアップファイルサイズ確認
        file_size = backup_path.stat().st_size
        logger.info(f"Backup file size: {file_size / (1024 * 1024):.2f} MB")

        if file_size == 0:
            logger.error("Backup file is empty")
            print("Error: Backup file is empty")
            backup_path.unlink()
            return

        print(f"Backup created: {backup_path}")
        logger.info(f"Backup created successfully: {backup_name}")

    except FileNotFoundError:
        logger.error("docker command not found. Please install Docker Desktop.")
        print("Error: docker command not found")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        if backup_path.exists():
            backup_path.unlink()
        return
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"pg_dump failed: {error_msg}")
        print(f"Error: pg_dump failed\n{error_msg}")
        if backup_path.exists():
            backup_path.unlink()
        return
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        if backup_path.exists():
            backup_path.unlink()
        return


def backup_postgresql():
    """PostgreSQL バックアップのエントリーポイント

    Docker コンテナが起動中の場合は docker exec を使用し、
    停止中の場合はホスト側の pg_dump にフォールバックします。
    """
    container_name = config.postgres.container.get_container_name()

    # コンテナ起動確認
    if DockerCommandExecutor.is_container_running(container_name):
        logger.info(f"Container {container_name} is running, using Docker exec")
        backup_postgresql_via_docker()
    else:
        logger.warning(
            f"Container {container_name} is not running, falling back to host pg_dump. "
            f"Consider running 'poetry run postgres_start' first."
        )
        backup_postgresql_via_host()


def main():
    logger.info("Starting database backup process")

    if config.db_type == 'sqlite':
        backup_sqlite()
    elif config.db_type == 'postgres':
        backup_postgresql()
    else:
        logger.error(f"Unsupported database type: {config.db_type}")
        print(f"Error: Unsupported database type: {config.db_type}")
        return

    logger.info("Database backup process completed")


if __name__ == "__main__":
    main()
