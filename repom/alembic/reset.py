"""Alembic migration reset functionality."""

from pathlib import Path
from sqlalchemy import create_engine, inspect, text


class AlembicReset:
    """Alembic マイグレーションのリセット機能"""

    def __init__(
        self,
        db_url: str,
        versions_dir: Path,
        version_table: str = "alembic_version",
        version_table_schema: str | None = None
    ):
        """
        Args:
            db_url: データベース URL
            versions_dir: マイグレーションファイルの保存場所
            version_table: Alembic バージョンテーブル名
            version_table_schema: Alembic バージョンテーブルのスキーマ（SQLite では無視）
        """
        self.db_url = db_url
        self.versions_dir = Path(versions_dir)
        self.version_table = version_table
        self.version_table_schema = version_table_schema

    def drop_alembic_version_table(self) -> None:
        """設定された Alembic バージョンテーブルを削除"""
        engine = create_engine(self.db_url)
        try:
            quoted_version_table = engine.dialect.identifier_preparer.quote(
                self.version_table
            )
            # SQLite has no real schema support, so the existence check (like
            # the DROP statement below) only qualifies by schema on postgresql.
            existence_schema = None
            if (
                self.db_url.startswith('postgresql')
                and self.version_table_schema is not None
            ):
                quoted_version_table = (
                    f"{engine.dialect.identifier_preparer.quote_schema(self.version_table_schema)}."
                    f"{quoted_version_table}"
                )
                existence_schema = self.version_table_schema

            with engine.connect() as conn:
                table_exists = inspect(conn).has_table(
                    self.version_table, schema=existence_schema
                )
                if table_exists:
                    conn.execute(text(f"DROP TABLE {quoted_version_table}"))
                    conn.commit()
                    print(f"[OK] Dropped {self.version_table} table")
                else:
                    print(f"[OK] {self.version_table} table does not exist")
        finally:
            # Undisposed engines keep a pooled connection open, which leaves
            # a file-based SQLite database locked on Windows until GC'd.
            engine.dispose()

    def delete_migration_files(self, versions_dir: Path | None = None) -> None:
        """マイグレーションファイルを削除

        Args:
            versions_dir: 削除対象のディレクトリ（省略時は self.versions_dir）
        """
        versions_dir = (
            Path(versions_dir) if versions_dir is not None else self.versions_dir
        )
        if not versions_dir.exists():
            print(f"[OK] Versions directory does not exist: {versions_dir}")
            return

        deleted_count = 0
        for file in versions_dir.glob("*.py"):
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
        pycache = versions_dir / "__pycache__"
        if pycache.exists():
            import shutil
            shutil.rmtree(pycache)
            print("[OK] Deleted __pycache__")
