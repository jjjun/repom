"""繝・・繧ｿ繝吶・繧ｹ繝ｪ繧ｹ繝医い繧ｹ繧ｯ繝ｪ繝励ヨ

繝舌ャ繧ｯ繧｢繝・・繝・ぅ繝ｬ繧ｯ繝医Μ縺九ｉ蟇ｾ隧ｱ逧・↓繝ｪ繧ｹ繝医い繝輔ぃ繧､繝ｫ繧帝∈謚槭＠縲・
繝・・繧ｿ繝吶・繧ｹ繧貞ｾｩ蜈・＠縺ｾ縺吶・

菴ｿ逕ｨ譁ｹ豕・
    uv run db_restore

    # 迺ｰ蠅・欠螳・
    EXEC_ENV=dev uv run db_restore
"""

from repom.config import config
from repom.logging import get_logger
from basekit.docker_manager import DockerCommandExecutor
import os
import shutil
import subprocess
import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional

from repom.scripts._backup_utils import (
    format_size,
    get_backups,
    run_postgres_via_docker_or_host,
)

logger = get_logger(__name__)


def display_backups(backups: list[Path]) -> Optional[Path]:
    """繝舌ャ繧ｯ繧｢繝・・荳隕ｧ繧定｡ｨ遉ｺ縺励√Θ繝ｼ繧ｶ繝ｼ縺ｫ驕ｸ謚槭＆縺帙ｋ

    Args:
        backups: 繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ縺ｮ繝ｪ繧ｹ繝・

    Returns:
        驕ｸ謚槭＆繧後◆繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ縲√∪縺溘・繧ｭ繝｣繝ｳ繧ｻ繝ｫ譎ゅ・ None
    """
    if not backups:
        print("No backups found")
        return None

    print("\nAvailable backups:")
    print("笏" * 60)

    for i, backup in enumerate(backups, 1):
        size = format_size(backup.stat().st_size)
        modified = datetime.fromtimestamp(backup.stat().st_mtime)
        modified_str = modified.strftime("%Y-%m-%d %H:%M:%S")
        latest_mark = " <- latest" if i == 1 else ""
        print(f"[{i}] {backup.name} ({size}) - {modified_str}{latest_mark}")

    print("笏" * 60)

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
    """SQLite 繝・・繧ｿ繝吶・繧ｹ縺ｮ繝ｪ繧ｹ繝医い蜃ｦ逅・

    Args:
        backup_file: 繝ｪ繧ｹ繝医い蜈・・繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ
    """
    logger.info(f"Starting SQLite restore from {backup_file.name}")

    current_db = Path(config.sqlite.db_file_path)

    # 迴ｾ蝨ｨ縺ｮ DB 縺悟ｭ伜惠縺吶ｋ蝣ｴ蜷医∬・蜍輔ヰ繝・け繧｢繝・・繧剃ｽ懈・
    if current_db.exists():
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        auto_backup_name = f"restore_backup_{now_str}.sqlite3"
        auto_backup_path = Path(config.db_backup_path) / auto_backup_name

        logger.info(f"Creating automatic backup of current database: {auto_backup_name}")
        print(f"Creating backup of current database: {auto_backup_name}")
        shutil.copy2(current_db, auto_backup_path)
        logger.debug(f"Backup saved to {auto_backup_path}")

    # 繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ繧堤樟蝨ｨ縺ｮ DB 縺ｫ荳頑嶌縺・
    try:
        logger.info(f"Restoring {backup_file.name} to {current_db}")
        shutil.copy2(backup_file, current_db)
        print("\n笨・Restore completed successfully")
        print(f"  Database: {current_db}")
        logger.info("SQLite restore completed successfully")
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\n笨・Restore failed: {e}")
        raise


def restore_postgresql_via_host(backup_file: Path):
    """PostgreSQL 繝・・繧ｿ繝吶・繧ｹ縺ｮ繝ｪ繧ｹ繝医い蜃ｦ逅・ｼ医・繧ｹ繝亥・ gunzip/psql 菴ｿ逕ｨ・・

    繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ螳溯｣・ｼ咼ocker 繧ｳ繝ｳ繝・リ縺瑚ｵｷ蜍輔＠縺ｦ縺・↑縺・ｴ蜷医↓菴ｿ逕ｨ縺輔ｌ縺ｾ縺吶・
    繝帙せ繝育腸蠅・↓ gunzip 縺ｨ psql 縺後う繝ｳ繧ｹ繝医・繝ｫ縺輔ｌ縺ｦ縺・ｋ蠢・ｦ√′縺ゅｊ縺ｾ縺吶・

    Args:
        backup_file: 繝ｪ繧ｹ繝医い蜈・・繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ (.sql.gz)
    """
    logger.info(f"Starting PostgreSQL restore from {backup_file.name}")

    try:
        # 迺ｰ蠅・､画焚縺ｫ PGPASSWORD 繧定ｨｭ螳・
        env = os.environ.copy()
        env['PGPASSWORD'] = config.postgres.password

        # gunzip + psql 縺ｧ繝ｪ繧ｹ繝医い
        logger.debug("Decompressing backup file")

        # gunzip 縺ｧ繝舌ャ繧ｯ繧｢繝・・繧定ｧ｣蜃阪＠縺ｪ縺後ｉ psql 縺ｫ繝代う繝・
        gunzip_proc = subprocess.Popen(
            ['gunzip', '-c', str(backup_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # psql 繧ｳ繝槭Φ繝峨〒繝ｪ繧ｹ繝医い
        psql_cmd = [
            'psql',
            '-h', config.postgres.host,
            '-p', str(config.postgres.port),
            '-U', config.postgres.user,
            '-d', config.postgres_db,
            '-v', 'ON_ERROR_STOP=1',  # 繧ｨ繝ｩ繝ｼ譎ゅ↓蛛懈ｭ｢
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

        # gunzip 縺ｮ stdout 繧・psql 縺御ｽｿ逕ｨ縺吶ｋ縺溘ａ close
        gunzip_proc.stdout.close()

        # 繝励Ο繧ｻ繧ｹ縺ｮ邨ゆｺ・ｒ蠕・▽
        psql_stdout, psql_stderr = psql_proc.communicate()
        gunzip_stderr = gunzip_proc.stderr.read()

        # gunzip 縺ｮ繧ｨ繝ｩ繝ｼ繝√ぉ繝・け
        if gunzip_proc.returncode != 0:
            error_msg = gunzip_stderr.decode('utf-8')
            logger.error(f"gunzip failed: {error_msg}")
            print(f"\n笨・Error: Failed to decompress backup file\n{error_msg}")
            return

        # psql 縺ｮ繧ｨ繝ｩ繝ｼ繝√ぉ繝・け
        if psql_proc.returncode != 0:
            error_msg = psql_stderr.decode('utf-8')
            logger.error(f"psql restore failed: {error_msg}")
            print(f"\n笨・Error: Restore failed\n{error_msg}")
            return

        print("\n笨・Restore completed successfully")
        print(f"  Database: {config.postgres_db}")
        logger.info("PostgreSQL restore completed successfully")

    except FileNotFoundError as e:
        if 'gunzip' in str(e):
            logger.error("gunzip command not found")
            print("\n笨・Error: gunzip command not found")
            print("Please install gzip utilities")
        elif 'psql' in str(e):
            logger.error("psql command not found")
            print("\n笨・Error: psql command not found")
            print("Please install PostgreSQL client tools and ensure 'psql' is in your PATH")
        else:
            logger.error(f"Command not found: {e}")
            print(f"\n笨・Error: Required command not found: {e}")
        return
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\n笨・Error: Restore failed: {e}")
        raise


def restore_postgresql_via_docker(backup_file: Path):
    """PostgreSQL 繝・・繧ｿ繝吶・繧ｹ縺ｮ繝ｪ繧ｹ繝医い蜃ｦ逅・ｼ・ocker exec 菴ｿ逕ｨ・・

    Docker 繧ｳ繝ｳ繝・リ蜀・・ psql 繧剃ｽｿ逕ｨ縺励※繝ｪ繧ｹ繝医い繧貞ｮ溯｡後＠縺ｾ縺吶・
    繝帙せ繝育腸蠅・↓ PostgreSQL 繧ｯ繝ｩ繧､繧｢繝ｳ繝医ヤ繝ｼ繝ｫ縺ｮ繧､繝ｳ繧ｹ繝医・繝ｫ縺ｯ荳崎ｦ√〒縺吶・

    Args:
        backup_file: 繝ｪ繧ｹ繝医い蜈・・繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ (.sql.gz)
    """
    logger.info(f"Starting PostgreSQL restore from {backup_file.name}")

    container_name = config.postgres.container.get_container_name()
    logger.info(f"Using Docker container: {container_name}")

    try:
        # 繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ繧定ｧ｣蜃・
        logger.debug("Decompressing backup file")
        with gzip.open(backup_file, 'rb') as gz_file:
            sql_data = gz_file.read()

        logger.debug(f"Backup file decompressed: {len(sql_data)} bytes")

        # psql 繧ｳ繝槭Φ繝画ｧ狗ｯ・
        psql_cmd = [
            "psql",
            "-U", config.postgres.user,
            "-d", config.postgres_db,
            "-v", "ON_ERROR_STOP=1",  # 繧ｨ繝ｩ繝ｼ譎ゅ↓蛛懈ｭ｢
        ]

        logger.debug(f"Executing: docker exec -i {container_name} {' '.join(psql_cmd)}")
        print("Restoring database...")

        # docker exec -i 縺ｧ psql 螳溯｡鯉ｼ・tdin 縺九ｉ SQL 繧呈ｳｨ蜈･・・
        DockerCommandExecutor.exec_command(
            container_name=container_name,
            command=psql_cmd,
            stdin=sql_data,
            capture_output=True
        )

        print("\n笨・Restore completed successfully")
        print(f"  Database: {config.postgres_db}")
        logger.info("PostgreSQL restore completed successfully")

    except FileNotFoundError:
        logger.error("docker command not found. Please install Docker Desktop.")
        print("\n笨・Error: docker command not found")
        print("Please install Docker Desktop: https://www.docker.com/products/docker-desktop")
        return
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"psql restore failed: {error_msg}")
        print(f"\n笨・Error: Restore failed\n{error_msg}")
        return
    except gzip.BadGzipFile:
        logger.error("Invalid gzip file")
        print("\n笨・Error: Invalid backup file (not a gzip file)")
        return
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        print(f"\n笨・Error: Restore failed: {e}")
        raise


def restore_postgresql(backup_file: Path):
    """PostgreSQL 繝ｪ繧ｹ繝医い縺ｮ繧ｨ繝ｳ繝医Μ繝ｼ繝昴う繝ｳ繝・

    Docker 繧ｳ繝ｳ繝・リ縺瑚ｵｷ蜍穂ｸｭ縺ｮ蝣ｴ蜷医・ docker exec 繧剃ｽｿ逕ｨ縺励・
    蛛懈ｭ｢荳ｭ縺ｮ蝣ｴ蜷医・繝帙せ繝亥・縺ｮ gunzip/psql 縺ｫ繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ縺励∪縺吶・

    Args:
        backup_file: 繝ｪ繧ｹ繝医い蜈・・繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ (.sql.gz)
    """
    run_postgres_via_docker_or_host(
        via_docker=lambda: restore_postgresql_via_docker(backup_file),
        via_host=lambda: restore_postgresql_via_host(backup_file),
        operation="restore",
    )


def main():
    logger.info("Starting database restore process")

    # 繝舌ャ繧ｯ繧｢繝・・繝・ぅ繝ｬ繧ｯ繝医Μ縺ｮ蟄伜惠遒ｺ隱・
    if not os.path.exists(config.db_backup_path):
        print(f"Error: Backup directory not found: {config.db_backup_path}")
        logger.error(f"Backup directory not found: {config.db_backup_path}")
        return

    # 繝舌ャ繧ｯ繧｢繝・・繝輔ぃ繧､繝ｫ繧貞叙蠕・
    backups = get_backups(config.db_backup_path, config.db_type)

    if not backups:
        print(f"No backups found in {config.db_backup_path}")
        logger.info("No backups found")
        return

    # 繝ｦ繝ｼ繧ｶ繝ｼ縺ｫ繝舌ャ繧ｯ繧｢繝・・繧帝∈謚槭＆縺帙ｋ
    selected = display_backups(backups)

    if not selected:
        logger.info("Restore cancelled by user")
        return

    # 遒ｺ隱阪Γ繝・そ繝ｼ繧ｸ
    print(f"\nSelected: {selected.name}")
    confirm = input(f"Confirm restore from {selected.name}? [y/N]: ").strip().lower()

    if confirm != 'y':
        print("Restore cancelled")
        logger.info("Restore cancelled by user")
        return

    # 繝輔ぃ繧､繝ｫ諡｡蠑ｵ蟄舌°繧・db_type 繧貞愛螳・
    is_sqlite = selected.suffix == '.sqlite3'
    is_postgres = selected.name.endswith('.sql.gz')

    # 繝ｪ繧ｹ繝医い螳溯｡・
    try:
        if is_sqlite and config.db_type == 'sqlite':
            restore_sqlite(selected)
        elif is_postgres and config.db_type == 'postgres':
            restore_postgresql(selected)
        else:
            print("\n笨・Error: Backup file type mismatch")
            print(f"  Current db_type: {config.db_type}")
            print(f"  Backup file: {selected.name}")
            logger.error(f"Backup file type mismatch: {config.db_type} vs {selected.name}")
            return

    except Exception as e:
        logger.error(f"Restore process failed: {e}")
        print("\n笨・Restore process failed")
        return

    logger.info("Database restore process completed")


if __name__ == "__main__":
    main()

