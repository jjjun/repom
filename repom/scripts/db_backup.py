from repom.config import config
from repom.logging import get_logger
from basekit.docker_manager import DockerCommandExecutor
import os
import subprocess
import gzip
from datetime import datetime
from pathlib import Path
from repom.scripts._backup_utils import (
    build_host_pg_env,
    cleanup_incomplete_backups,
    ensure_backup_dir,
    format_size,
    open_backup_temp_file,
    rotate_backups,
    run_postgres_via_docker_or_host,
    snapshot_sqlite_database,
    write_checksum,
)

# ロガーを取得
logger = get_logger(__name__)

# Maximum number of backups to keep per database name
MAX_BACKUPS_PER_DB = 3


def cleanup_stale_backups(backup_dir: Path, glob_pattern: str):
    """Remove artifacts left by interrupted backup attempts."""
    for incomplete_backup in cleanup_incomplete_backups(backup_dir, glob_pattern):
        logger.warning(f"Removed incomplete backup: {incomplete_backup.name}")


def backup_sqlite():
    """SQLite データベースのバックアップ処理"""
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database file: {config.sqlite.db_file_path}")

    # Ensure backup directory exists with restrictive permissions
    ensure_backup_dir(config.db_backup_path)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Get original db file name and extension
    base_name = os.path.basename(config.sqlite.db_file_path)
    name, ext = os.path.splitext(base_name)
    # Format datetime (no milliseconds)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create backup file name: <name>_<datetime><ext>
    backup_name = f"{name}_{now_str}{ext}"
    backup_path = Path(config.db_backup_path) / backup_name
    partial_path = backup_path.with_name(f"{backup_path.name}.partial")
    logger.debug(f"Backup file name: {backup_name}")

    backup_dir = Path(config.db_backup_path)
    backup_pattern = f"{name}_*{ext}"
    cleanup_stale_backups(backup_dir, backup_pattern)

    # Snapshot through SQLite's backup API, keeping the backup readable only
    # by its owner from creation, so committed-but-uncheckpointed WAL data is
    # included instead of copying a raw file that may not be a consistent
    # point-in-time image while another connection holds it open.
    logger.debug(f"Backing up {config.sqlite.db_file_path} to {partial_path}")
    open_backup_temp_file(partial_path).close()
    try:
        snapshot_sqlite_database(Path(config.sqlite.db_file_path), partial_path)
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise
    if partial_path.stat().st_size == 0:
        logger.error("Backup file is empty")
        print("Error: Backup file is empty")
        partial_path.unlink()
        return

    partial_path.replace(backup_path)
    write_checksum(backup_path)
    removed = rotate_backups(backup_dir, backup_pattern, MAX_BACKUPS_PER_DB)
    if removed:
        logger.info(f"Removing {len(removed)} old backup(s) to maintain limit of {MAX_BACKUPS_PER_DB}")
        for old in removed:
            print(f"Removed old backup: {old.name}")
            logger.warning(f"Removed old backup: {old.name}")
    print(f"Backup created: {backup_path}")
    logger.info(f"Backup created successfully: {backup_name}")


def backup_postgresql_via_host():
    """PostgreSQL データベースのバックアップ処理（ホスト側 pg_dump 使用）

    フォールバック実装：Docker コンテナが起動していない場合に使用されます。
    ホスト環境に pg_dump がインストールされている必要があります。
    """
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database: {config.postgres_db}")

    # sslmode / sslrootcert を解決・検証する（db_url と同じロジックを共有）。
    # subprocess を起動する前に検証することで、prod での弱い sslmode を
    # プロセス起動前に拒否する。
    tls = config.postgres_tls_settings()

    # Ensure backup directory exists with restrictive permissions
    ensure_backup_dir(config.db_backup_path)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Create backup file name: db_<datetime>.sql.gz
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"db_{now_str}.sql.gz"
    backup_path = Path(config.db_backup_path) / backup_name
    partial_path = backup_path.with_name(f"{backup_path.name}.partial")
    logger.debug(f"Backup file name: {backup_name}")

    backup_dir = Path(config.db_backup_path)
    cleanup_stale_backups(backup_dir, "db_*.sql.gz")

    # pg_dump コマンド実行
    try:
        logger.info("Starting pg_dump process")
        env = build_host_pg_env(config.postgres.password, tls.sslmode, tls.sslrootcert)

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

        # gzip 圧縮 (0600 で作成し、一時ファイルが world-readable になる窓を作らない)
        with open_backup_temp_file(partial_path) as raw_file:
            with gzip.open(raw_file, 'wb') as gz_file:
                for line in pg_dump_proc.stdout:
                    gz_file.write(line)

        # pg_dump の終了を待つ
        _, stderr = pg_dump_proc.communicate()

        if pg_dump_proc.returncode != 0:
            error_msg = stderr.decode('utf-8')
            logger.error(f"pg_dump failed: {error_msg}")
            print(f"Error: pg_dump failed\n{error_msg}")
            if partial_path.exists():
                partial_path.unlink()  # 失敗したバックアップファイルを削除
            raise RuntimeError(f"pg_dump failed with exit code {pg_dump_proc.returncode}: {error_msg}")

        # バックアップファイルサイズ確認
        file_size = partial_path.stat().st_size
        logger.info(f"Backup file size: {format_size(file_size)}")

        if file_size == 0:
            logger.error("Backup file is empty")
            print("Error: Backup file is empty")
            partial_path.unlink()
            return

        partial_path.replace(backup_path)
        write_checksum(backup_path)
        removed = rotate_backups(backup_dir, "db_*.sql.gz", MAX_BACKUPS_PER_DB)
        if removed:
            logger.info(f"Removing {len(removed)} old backup(s) to maintain limit of {MAX_BACKUPS_PER_DB}")
            for old in removed:
                print(f"Removed old backup: {old.name}")
                logger.warning(f"Removed old backup: {old.name}")
        print(f"Backup created: {backup_path}")
        logger.info(f"Backup created successfully: {backup_name}")

    except FileNotFoundError:
        logger.error("pg_dump command not found. Please install PostgreSQL client tools.")
        print("Error: pg_dump command not found")
        print("Please install PostgreSQL client tools and ensure 'pg_dump' is in your PATH")
        return
    except RuntimeError:
        # pg_dump exited non-zero; already logged, printed, and cleaned up above.
        raise
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        if partial_path.exists():
            partial_path.unlink()
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

    # Ensure backup directory exists with restrictive permissions
    ensure_backup_dir(config.db_backup_path)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Create backup file name: db_<datetime>.sql.gz
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"db_{now_str}.sql.gz"
    backup_path = Path(config.db_backup_path) / backup_name
    partial_path = backup_path.with_name(f"{backup_path.name}.partial")
    logger.debug(f"Backup file name: {backup_name}")

    backup_dir = Path(config.db_backup_path)
    cleanup_stale_backups(backup_dir, "db_*.sql.gz")

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

        # gzip 圧縮して保存 (0600 で作成)
        with open_backup_temp_file(partial_path) as raw_file:
            with gzip.open(raw_file, 'wb') as gz_file:
                gz_file.write(result.stdout)

        # バックアップファイルサイズ確認
        file_size = partial_path.stat().st_size
        logger.info(f"Backup file size: {format_size(file_size)}")

        if file_size == 0:
            logger.error("Backup file is empty")
            print("Error: Backup file is empty")
            partial_path.unlink()
            return

        partial_path.replace(backup_path)
        write_checksum(backup_path)
        removed = rotate_backups(backup_dir, "db_*.sql.gz", MAX_BACKUPS_PER_DB)
        if removed:
            logger.info(f"Removing {len(removed)} old backup(s) to maintain limit of {MAX_BACKUPS_PER_DB}")
            for old in removed:
                print(f"Removed old backup: {old.name}")
                logger.warning(f"Removed old backup: {old.name}")
        print(f"Backup created: {backup_path}")
        logger.info(f"Backup created successfully: {backup_name}")

    except FileNotFoundError:
        logger.error("docker command not found. Please install Docker Desktop.")
        print("Error: docker command not found")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        if partial_path.exists():
            partial_path.unlink()
        return
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"pg_dump failed: {error_msg}")
        print(f"Error: pg_dump failed\n{error_msg}")
        if partial_path.exists():
            partial_path.unlink()
        return
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        if partial_path.exists():
            partial_path.unlink()
        return


def backup_postgresql():
    """PostgreSQL バックアップのエントリーポイント

    Docker コンテナが起動中の場合は docker exec を使用し、
    停止中の場合はホスト側の pg_dump にフォールバックします。
    """
    run_postgres_via_docker_or_host(
        via_docker=backup_postgresql_via_docker,
        via_host=backup_postgresql_via_host,
        operation="backup",
        host_tools="host pg_dump",
    )


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

