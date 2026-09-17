"""Alembic マイグレーションのリセットスクリプト

config から設定を取得して AlembicSetup を実行。
"""
import argparse

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
    args = parser.parse_args()

    confirm_destructive_operation(
        operation="reset Alembic migrations",
        target=safe_db_url(config.db_url),
        exec_env=config.exec_env,
        yes=args.yes,
    )

    setup = AlembicSetup(
        project_root=config.root_path,
        db_url=config.db_url
    )

    print("Resetting Alembic migrations...")
    setup.reset_migrations()
    print("[OK] Alembic migrations reset successfully")


if __name__ == "__main__":
    main()
