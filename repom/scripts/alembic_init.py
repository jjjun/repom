"""Alembic の初回セットアップスクリプト

config から設定を取得して AlembicSetup を実行。
"""
from repom.alembic.setup import AlembicSetup
from repom.config import config


def main():
    setup = AlembicSetup(
        project_root=config.root_path,
        db_url=config.db_url
    )

    print("Initializing Alembic...")
    setup.create_alembic_ini()
    setup.create_version_directory()
    print("\n✓ Alembic initialized successfully")
    print(f"  - alembic.ini: {config.root_path}/alembic.ini")
    print(f"  - versions dir: {setup.versions_dir}")
    print("\nNote: env.py and script.py.mako are provided by repom.")


if __name__ == "__main__":
    main()
