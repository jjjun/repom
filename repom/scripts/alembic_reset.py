"""Alembic マイグレーションのリセットスクリプト

config から設定を取得して AlembicSetup を実行。
"""
from repom.alembic.setup import AlembicSetup
from repom.config import config


def main():
    setup = AlembicSetup(
        project_root=config.root_path,
        db_url=config.db_url
    )

    print("Resetting Alembic migrations...")
    setup.reset_migrations()
    print("✓ Alembic migrations reset successfully")


if __name__ == "__main__":
    main()
