"""Alembic マイグレーションのリセットスクリプト

alembic.ini から設定を取得して AlembicSetup を実行。
alembic.ini がマイグレーションの配置場所の唯一の情報源であるため、
project_root からデフォルトを組み立てず、指定された ini ファイルを読む。
"""
import argparse
from pathlib import Path

from repom.alembic.setup import AlembicSetup
from repom.config import config
from repom.database import safe_db_url
from repom.scripts._destructive import confirm_destructive_operation


def main():
    parser = argparse.ArgumentParser(
        description="Drop the Alembic version table and delete migration files."
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip the interactive confirmation prompt (required when stdin is not a TTY).",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to the alembic.ini to reset (default: <root_path>/alembic.ini).",
    )
    args = parser.parse_args()

    ini_path = (
        Path(args.config) if args.config
        else Path(config.root_path) / "alembic.ini"
    )
    if not ini_path.is_file():
        print(f"Alembic config file not found: {ini_path}")
        raise SystemExit(1)

    setup = AlembicSetup.from_ini(ini_path, config.db_url)

    version_table_display = setup.version_table or "alembic_version"
    if setup.version_table_schema:
        version_table_display = (
            f"{setup.version_table_schema}.{version_table_display}"
        )
    versions_dirs_display = ", ".join(
        str(versions_dir) for versions_dir in setup.versions_dirs
    )

    confirm_destructive_operation(
        operation="reset Alembic migrations",
        target=(
            f"{safe_db_url(config.db_url)} "
            f"(version table: {version_table_display}; "
            f"version directories: {versions_dirs_display})"
        ),
        exec_env=config.exec_env,
        yes=args.yes,
    )

    print("Resetting Alembic migrations...")
    setup.reset_migrations()
    print("[OK] Alembic migrations reset successfully")


if __name__ == "__main__":
    main()
