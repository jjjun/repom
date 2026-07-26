"""Alembic migration reset functionality."""

from pathlib import Path
from sqlalchemy import create_engine, text


class AlembicReset:
    """Alembic マイグレーションのリセット機能"""

    def __init__(
        self,
        db_url: str,
        versions_dir: Path,
        version_table: str = "alembic_version"
    ):
        """
        Args:
            db_url: データベース URL
            versions_dir: マイグレーションファイルの保存場所
            version_table: Alembic バージョンテーブル名
        """
        self.db_url = db_url
        self.versions_dir = Path(versions_dir)
        self.version_table = version_table

    def drop_alembic_version_table(self) -> None:
        """設定された Alembic バージョンテーブルを削除"""
        engine = create_engine(self.db_url)
        quoted_version_table = engine.dialect.identifier_preparer.quote(
            self.version_table
        )

        with engine.connect() as conn:
            # データベースタイプに応じたテーブル存在チェック
            if self.db_url.startswith('postgresql'):
                result = conn.execute(text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "AND table_name = :version_table"
                ), {"version_table": self.version_table})
            else:
                # SQLite
                result = conn.execute(text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name=:version_table"
                ), {"version_table": self.version_table})

            if result.fetchone():
                conn.execute(text(f"DROP TABLE {quoted_version_table}"))
                conn.commit()
                print(f"[OK] Dropped {self.version_table} table")
            else:
                print(f"[OK] {self.version_table} table does not exist")

    def delete_migration_files(self) -> None:
        """マイグレーションファイルを削除"""
        if not self.versions_dir.exists():
            print(f"[OK] Versions directory does not exist: {self.versions_dir}")
            return

        deleted_count = 0
        for file in self.versions_dir.glob("*.py"):
            # __init__.py は保持
            if file.name == "__init__.py":
                continue

            file.unlink()
            deleted_count += 1
            print(f"  - Deleted: {file.name}")

        if deleted_count > 0:
            print(f"[OK] Deleted {deleted_count} migration file(s)")
        else:
            print("[OK] No migration files to delete")

        # __pycache__ も削除
        pycache = self.versions_dir / "__pycache__"
        if pycache.exists():
            import shutil
            shutil.rmtree(pycache)
            print("✓ Deleted __pycache__")
