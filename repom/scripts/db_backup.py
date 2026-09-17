from repom.config import config
from repom.logging import get_logger
from basekit.docker_manager import DockerCommandExecutor
import os
import re
import gzip
from datetime import datetime
from pathlib import Path
from repom.scripts._backup_utils import (
    BackupError,
    ByteCountingWriter,
    backup_name_pattern,
    build_host_pg_env,
    build_pg_client_command,
    cleanup_incomplete_backups,
    ensure_backup_dir,
    open_backup_temp_file,
    publish_backup,
    run_postgres_via_docker_or_host,
    run_streaming_command,
    snapshot_sqlite_database,
)

# ロガーを取得
logger = get_logger(__name__)

# Maximum number of backups to keep per database name
MAX_BACKUPS_PER_DB = 3


def cleanup_stale_backups(
    backup_dir: Path, glob_pattern: str, name_pattern: re.Pattern[str] | None = None
):
    """Remove artifacts left by interrupted backup attempts."""
    for incomplete_backup in cleanup_incomplete_backups(backup_dir, glob_pattern, name_pattern):
        logger.warning(f"Removed incomplete backup: {incomplete_backup.name}")


def backup_sqlite():
    """SQLite データベースのバックアップ処理"""
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database file: {config.sqlite.db_file_path}")

    # Ensure backup directory exists with restrictive permissions
    try:
        ensure_backup_dir(config.db_backup_path)
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        raise BackupError(f"Backup failed: {e}") from e
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
    name_pattern = backup_name_pattern(name, ext)
    cleanup_stale_backups(backup_dir, backup_pattern, name_pattern)

    # Snapshot through SQLite's backup API, keeping the backup readable only
    # by its owner from creation, so committed-but-uncheckpointed WAL data is
    # included instead of copying a raw file that may not be a consistent
    # point-in-time image while another connection holds it open.
    logger.debug(f"Backing up {config.sqlite.db_file_path} to {partial_path}")
    try:
        open_backup_temp_file(partial_path).close()
    except OSError as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        raise BackupError(f"Backup failed: {e}") from e

    try:
        snapshot_sqlite_database(Path(config.sqlite.db_file_path), partial_path)
        publish_backup(
            partial_path,
            backup_path,
            backup_dir,
            backup_pattern,
            MAX_BACKUPS_PER_DB,
            name_pattern,
            empty=partial_path.stat().st_size == 0,
            empty_message="SQLite backup produced an empty file",
        )
    except BackupError:
        # Empty backup file; already logged, printed, and cleaned up above.
        raise
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        if partial_path.exists():
            partial_path.unlink()
        raise BackupError(f"Backup failed: {e}") from e


def _pg_dump_command(container_name: str | None) -> list[str]:
    """Build the pg_dump argv for the host or Docker path.

    A separate function (rather than inlining build_pg_client_command below)
    so tests can substitute a stand-in child process while still exercising
    the real Popen-based streaming path in _backup_postgresql.
    """
    return build_pg_client_command(
        "pg_dump",
        host=config.postgres.host,
        port=config.postgres.port,
        user=config.postgres.user,
        database=config.postgres_db,
        extra_args=[
            "--clean",      # DROP statements を含める
            "--if-exists",  # DROP IF EXISTS で中断防止
            "--no-owner",   # OWNER設定を出力しない
            "--no-acl",     # ACL設定を出力しない
        ],
        container_name=container_name,
    )


def _backup_postgresql(container_name: str | None) -> None:
    """PostgreSQL データベースのバックアップ処理（ホスト / Docker exec 共通）

    ``container_name`` が None ならホストの pg_dump を直接実行し、そうでなければ
    その名前のコンテナへ docker exec 経由で実行する。pg_dump の stdout は
    gzip 圧縮しながらそのまま partial ファイルへストリームし（メモリに全体を
    保持しない）、stderr は別スレッドでドレインしてデッドロックを防ぐ
    （repom#167）。
    """
    logger.debug(f"Backup directory: {config.db_backup_path}")
    logger.debug(f"Database: {config.postgres_db}")

    env = None
    if container_name is None:
        # sslmode / sslrootcert を解決・検証する（db_url と同じロジックを共有）。
        # subprocess を起動する前に検証することで、prod での弱い sslmode を
        # プロセス起動前に拒否する。
        tls = config.postgres_tls_settings()
        env = build_host_pg_env(config.postgres.password, tls.sslmode, tls.sslrootcert)

    # Ensure backup directory exists with restrictive permissions
    ensure_backup_dir(config.db_backup_path)
    logger.debug(f"Backup directory created/verified: {config.db_backup_path}")

    # Create backup file name: <postgres_db>_<datetime>.sql.gz
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{config.postgres_db}_{now_str}.sql.gz"
    backup_path = Path(config.db_backup_path) / backup_name
    partial_path = backup_path.with_name(f"{backup_path.name}.partial")
    logger.debug(f"Backup file name: {backup_name}")

    backup_dir = Path(config.db_backup_path)
    backup_pattern = f"{config.postgres_db}_*.sql.gz"
    name_pattern = backup_name_pattern(config.postgres_db, ".sql.gz")
    cleanup_stale_backups(backup_dir, backup_pattern, name_pattern)

    command = _pg_dump_command(container_name)
    logger.info("Starting pg_dump via Docker exec" if container_name else "Starting pg_dump process")
    logger.debug(f"Executing: {' '.join(command)} (PGPASSWORD hidden)")

    try:
        raw_file = open_backup_temp_file(partial_path)
    except OSError as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        raise BackupError(f"Backup failed: {e}") from e

    try:
        # gzip 圧縮 (0600 で作成し、一時ファイルが world-readable になる窓を作らない)
        with raw_file:
            with gzip.open(raw_file, 'wb') as gz_file:
                writer = ByteCountingWriter(gz_file)
                result = run_streaming_command(
                    command, env=env, stdout_file=writer, password=config.postgres.password
                )
        bytes_written = writer.bytes_written

        if result.returncode != 0:
            logger.error(f"pg_dump failed: {result.stderr}")
            print(f"Error: pg_dump failed\n{result.stderr}")
            if partial_path.exists():
                partial_path.unlink()  # 失敗したバックアップファイルを削除
            raise BackupError(f"pg_dump failed with exit code {result.returncode}: {result.stderr}")

        # 空判定は pg_dump から読んだ生バイト数で行う (gzip ヘッダーで
        # partial ファイル自体は常に非ゼロになるため)
        publish_backup(
            partial_path,
            backup_path,
            backup_dir,
            backup_pattern,
            MAX_BACKUPS_PER_DB,
            name_pattern,
            empty=bytes_written == 0,
            empty_message="pg_dump produced an empty backup",
        )

    except FileNotFoundError as e:
        if partial_path.exists():
            partial_path.unlink()
        if container_name is None:
            logger.error("pg_dump command not found. Please install PostgreSQL client tools.")
            print("Error: pg_dump command not found")
            print("Please install PostgreSQL client tools and ensure 'pg_dump' is in your PATH")
            raise BackupError("pg_dump command not found") from e
        logger.error("docker command not found. Please install Docker Desktop.")
        print("Error: docker command not found")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        raise BackupError("docker command not found") from e
    except BackupError:
        # pg_dump exited non-zero or produced an empty backup; already logged,
        # printed, and cleaned up above.
        raise
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"Error: Backup failed: {e}")
        if partial_path.exists():
            partial_path.unlink()
        raise BackupError(f"Backup failed: {e}") from e


def backup_postgresql_via_host():
    """PostgreSQL データベースのバックアップ処理（ホスト側 pg_dump 使用）

    フォールバック実装：Docker コンテナが起動していない場合に使用されます。
    ホスト環境に pg_dump がインストールされている必要があります。
    """
    _backup_postgresql(container_name=None)


def backup_postgresql_via_docker():
    """PostgreSQL データベースのバックアップ処理（Docker exec 使用）

    Docker コンテナ内の pg_dump を使用してバックアップを作成します。
    ホスト環境に PostgreSQL クライアントツールのインストールは不要です。
    """
    container_name = config.postgres.container.get_container_name()
    logger.info(f"Using Docker container: {container_name}")
    _backup_postgresql(container_name=container_name)


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

    logger.info("Database backup process completed")


if __name__ == "__main__":
    main()

