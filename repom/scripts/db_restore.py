"""データベースリストアスクリプト

バックアップディレクトリから対話的にリストアファイルを選択し、
データベースを復元します。

使用方法:
    poetry run db_restore

    # 環境指定
    EXEC_ENV=dev poetry run db_restore
"""

from repom.config import config
from repom.logging import get_logger
from repom._.docker_manager import DockerCommandExecutor
import os
import shutil
import subprocess
import gzip
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = get_logger(__name__)


def format_size(size_bytes: int) -> str:
    """ファイルサイズを MB 形式でフォーマット

    Args:
        size_bytes: バイト単位のファイルサイズ

    Returns:
        フォーマットされたサイズ文字列 (e.g., "2.50 MB")
    """
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_backups(backup_dir: str) -> List[Path]:
    """バックアップファイルを最新順に取得

    Args:
        backup_dir: バックアップディレクトリパス

    Returns:
        バックアップファイルのリスト（最新順）
    """
    if not os.path.exists(backup_dir):
        return []

    backup_path = Path(backup_dir)

    # SQLite と PostgreSQL 両方のバックアップファイルを検出
    sqlite_backups = list(backup_path.glob("*.sqlite3"))
    postgres_backups = list(backup_path.glob("db_*.sql.gz"))

    all_backups = sqlite_backups + postgres_backups

    # 最新順にソート（作成日時の降順）
    all_backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    return all_backups


def display_backups(backups: List[Path]) -> Optional[Path]:
    """バックアップ一覧を表示し、ユーザーに選択させる

    Args:
        backups: バックアップファイルのリスト

    Returns:
        選択されたバックアップファイル、またはキャンセル時は None
    """
    if not backups:
        print("No backups found")
        return None

    print("\nAvailable backups:")
    print("─" * 60)

    for i, backup in enumerate(backups, 1):
        size = format_size(backup.stat().st_size)
        modified = datetime.fromtimestamp(backup.stat().st_mtime)
        modified_str = modified.strftime("%Y-%m-%d %H:%M:%S")
        latest_mark = " <- latest" if i == 1 else ""
        print(f"[{i}] {backup.name} ({size}) - {modified_str}{latest_mark}")

    print("─" * 60)

    while True:
        user_input = input("\nSelect backup number to restore (or 'q' to cancel): ").strip()

        if user_input.lower() == 'q':
            print("Restore cancelled")
            return None

        try:
            index = int(user_input) - 1
            if 0 <= index < len(backups):
                return backups[index]
            else:
                print(f"Invalid number. Please enter 1-{len(backups)}")
        except ValueError:
            print("Invalid input. Please enter a number or 'q'")


def restore_sqlite(backup_file: Path):
    """SQLite データベースのリストア処理

    Args:
        backup_file: リストア元のバックアップファイル
    """
    logger.info(f"Starting SQLite restore from {backup_file.name}")

    current_db = Path(config.sqlite.db_file_path)

    # 現在の DB が存在する場合、自動バックアップを作成
    if current_db.exists():
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        auto_backup_name = f"restore_backup_{now_str}.sqlite3"
        auto_backup_path = Path(config.db_backup_path) / auto_backup_name

        logger.info(f"Creating automatic backup of current database: {auto_backup_name}")
        print(f"Creating backup of current database: {auto_backup_name}")
        shutil.copy2(current_db, auto_backup_path)
        logger.debug(f"Backup saved to {auto_backup_path}")

    # バックアップファイルを現在の DB に上書き
    try:
        logger.info(f"Restoring {backup_file.name} to {current_db}")
        shutil.copy2(backup_file, current_db)
        print(f"\n✓ Restore completed successfully")
        print(f"  Database: {current_db}")
        logger.info("SQLite restore completed successfully")
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\n✗ Restore failed: {e}")
        raise


def restore_postgresql_via_host(backup_file: Path):
    """PostgreSQL データベースのリストア処理（ホスト側 gunzip/psql 使用）

    フォールバック実装：Docker コンテナが起動していない場合に使用されます。
    ホスト環境に gunzip と psql がインストールされている必要があります。

    Args:
        backup_file: リストア元のバックアップファイル (.sql.gz)
    """
    logger.info(f"Starting PostgreSQL restore from {backup_file.name}")

    try:
        # 環境変数に PGPASSWORD を設定
        env = os.environ.copy()
        env['PGPASSWORD'] = config.postgres.password

        # gunzip + psql でリストア
        logger.debug("Decompressing backup file")

        # gunzip でバックアップを解凍しながら psql にパイプ
        gunzip_proc = subprocess.Popen(
            ['gunzip', '-c', str(backup_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # psql コマンドでリストア
        psql_cmd = [
            'psql',
            '-h', config.postgres.host,
            '-p', str(config.postgres.port),
            '-U', config.postgres.user,
            '-d', config.postgres_db,
            '-v', 'ON_ERROR_STOP=1',  # エラー時に停止
        ]

        logger.debug(f"Executing: {' '.join(psql_cmd)} (PGPASSWORD hidden)")
        print("Restoring database...")

        psql_proc = subprocess.Popen(
            psql_cmd,
            stdin=gunzip_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # gunzip の stdout を psql が使用するため close
        gunzip_proc.stdout.close()

        # プロセスの終了を待つ
        psql_stdout, psql_stderr = psql_proc.communicate()
        gunzip_stderr = gunzip_proc.stderr.read()

        # gunzip のエラーチェック
        if gunzip_proc.returncode != 0:
            error_msg = gunzip_stderr.decode('utf-8')
            logger.error(f"gunzip failed: {error_msg}")
            print(f"\n✗ Error: Failed to decompress backup file\n{error_msg}")
            return

        # psql のエラーチェック
        if psql_proc.returncode != 0:
            error_msg = psql_stderr.decode('utf-8')
            logger.error(f"psql restore failed: {error_msg}")
            print(f"\n✗ Error: Restore failed\n{error_msg}")
            return

        print(f"\n✓ Restore completed successfully")
        print(f"  Database: {config.postgres_db}")
        logger.info("PostgreSQL restore completed successfully")

    except FileNotFoundError as e:
        if 'gunzip' in str(e):
            logger.error("gunzip command not found")
            print("\n✗ Error: gunzip command not found")
            print("Please install gzip utilities")
        elif 'psql' in str(e):
            logger.error("psql command not found")
            print("\n✗ Error: psql command not found")
            print("Please install PostgreSQL client tools and ensure 'psql' is in your PATH")
        else:
            logger.error(f"Command not found: {e}")
            print(f"\n✗ Error: Required command not found: {e}")
        return
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\n✗ Error: Restore failed: {e}")
        raise


def restore_postgresql_via_docker(backup_file: Path):
    """PostgreSQL データベースのリストア処理（Docker exec 使用）

    Docker コンテナ内の psql を使用してリストアを実行します。
    ホスト環境に PostgreSQL クライアントツールのインストールは不要です。

    Args:
        backup_file: リストア元のバックアップファイル (.sql.gz)
    """
    logger.info(f"Starting PostgreSQL restore from {backup_file.name}")

    container_name = config.postgres.container.get_container_name()
    logger.info(f"Using Docker container: {container_name}")

    try:
        # バックアップファイルを解凍
        logger.debug("Decompressing backup file")
        with gzip.open(backup_file, 'rb') as gz_file:
            sql_data = gz_file.read()

        logger.debug(f"Backup file decompressed: {len(sql_data)} bytes")

        # psql コマンド構築
        psql_cmd = [
            "psql",
            "-U", config.postgres.user,
            "-d", config.postgres_db,
            "-v", "ON_ERROR_STOP=1",  # エラー時に停止
        ]

        logger.debug(f"Executing: docker exec -i {container_name} {' '.join(psql_cmd)}")
        print("Restoring database...")

        # docker exec -i で psql 実行（stdin から SQL を注入）
        result = DockerCommandExecutor.exec_command(
            container_name=container_name,
            command=psql_cmd,
            stdin=sql_data,
            capture_output=True
        )

        print(f"\n✓ Restore completed successfully")
        print(f"  Database: {config.postgres_db}")
        logger.info("PostgreSQL restore completed successfully")

    except FileNotFoundError:
        logger.error("docker command not found. Please install Docker Desktop.")
        print("\n✗ Error: docker command not found")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        return
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"psql restore failed: {error_msg}")
        print(f"\n✗ Error: Restore failed\n{error_msg}")
        return
    except gzip.BadGzipFile:
        logger.error("Invalid gzip file")
        print(f"\n✗ Error: Invalid backup file (not a gzip file)")
        return
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\n✗ Error: Restore failed: {e}")
        raise


def restore_postgresql(backup_file: Path):
    """PostgreSQL リストアのエントリーポイント

    Docker コンテナが起動中の場合は docker exec を使用し、
    停止中の場合はホスト側の gunzip/psql にフォールバックします。

    Args:
        backup_file: リストア元のバックアップファイル (.sql.gz)
    """
    container_name = config.postgres.container.get_container_name()

    # コンテナ起動確認
    if DockerCommandExecutor.is_container_running(container_name):
        logger.info(f"Container {container_name} is running, using Docker exec")
        restore_postgresql_via_docker(backup_file)
    else:
        logger.warning(
            f"Container {container_name} is not running, falling back to host tools. "
            f"Consider running 'poetry run postgres_start' first."
        )
        restore_postgresql_via_host(backup_file)


def main():
    logger.info("Starting database restore process")

    # バックアップディレクトリの存在確認
    if not os.path.exists(config.db_backup_path):
        print(f"Error: Backup directory not found: {config.db_backup_path}")
        logger.error(f"Backup directory not found: {config.db_backup_path}")
        return

    # バックアップファイルを取得
    backups = get_backups(config.db_backup_path)

    if not backups:
        print(f"No backups found in {config.db_backup_path}")
        logger.info("No backups found")
        return

    # ユーザーにバックアップを選択させる
    selected = display_backups(backups)

    if not selected:
        logger.info("Restore cancelled by user")
        return

    # 確認メッセージ
    print(f"\nSelected: {selected.name}")
    confirm = input(f"Confirm restore from {selected.name}? [y/N]: ").strip().lower()

    if confirm != 'y':
        print("Restore cancelled")
        logger.info("Restore cancelled by user")
        return

    # ファイル拡張子から db_type を判定
    is_sqlite = selected.suffix == '.sqlite3'
    is_postgres = selected.name.endswith('.sql.gz')

    # リストア実行
    try:
        if is_sqlite and config.db_type == 'sqlite':
            restore_sqlite(selected)
        elif is_postgres and config.db_type == 'postgres':
            restore_postgresql(selected)
        else:
            print(f"\n✗ Error: Backup file type mismatch")
            print(f"  Current db_type: {config.db_type}")
            print(f"  Backup file: {selected.name}")
            logger.error(f"Backup file type mismatch: {config.db_type} vs {selected.name}")
            return

    except Exception as e:
        logger.error(f"Restore process failed: {e}")
        print(f"\n✗ Restore process failed")
        return

    logger.info("Database restore process completed")


if __name__ == "__main__":
    main()
