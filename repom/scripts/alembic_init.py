"""Alembic の初回セットアップスクリプト

config から設定を取得して AlembicSetup を実行。
alembic.ini が既に存在する場合は、そこに記載された version_locations を
使ってバージョンディレクトリを作成する（デフォルトの場所ではなく）。
"""
from pathlib import Path

from repom.alembic.setup import AlembicSetup
from repom.config import config


def main():
    ini_path = Path(config.root_path) / "alembic.ini"

    if ini_path.exists():
        setup = AlembicSetup.from_ini(ini_path, config.db_url)
    else:
        setup = AlembicSetup(
            project_root=config.root_path,
            db_url=config.db_url
        )

    print("Initializing Alembic...")
    setup.create_alembic_ini()
    setup.create_version_directory()
    print("\n[OK] Alembic initialized successfully")
    print(f"  - alembic.ini: {config.root_path}/alembic.ini")
    print(f"  - versions dir: {setup.versions_dir}")
    print("\nNote: env.py and script.py.mako are provided by repom.")


if __name__ == "__main__":
    main()
