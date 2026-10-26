"""Alembic migration reset functionality."""

from collections.abc import Iterable
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

from repom.exceptions import UnsafeVersionsDirectoryError


def is_project_directory(path: Path, project_dirs: Iterable[Path] = ()) -> bool:
    """path が project_dirs または config.root_path と同じディレクトリか判定

    versions ディレクトリがこれらに一致すると、プロジェクト直下の *.py が
    マイグレーションファイルとして削除対象になる。
    """
    # この module では repom.config を module level で import しない。CONFIG_HOOK の
    # module は repom.config の初期化中に import され、repom.alembic (例:
    # repom.alembic.constants) を import することがあり、循環してしまうため。
    from repom.config import config

    candidates = [Path(project_dir) for project_dir in project_dirs]
    if config.root_path:
        candidates.append(Path(config.root_path))
    resolved = Path(path).resolve()
    return any(resolved == candidate.resolve() for candidate in candidates)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


class AlembicReset:
    """Alembic マイグレーションのリセット機能"""

    def __init__(
        self,
        db_url: str,
        versions_dir: Path,
        version_table: str = "alembic_version",
        version_table_schema: str | None = None,
        project_dirs: Iterable[Path] = (),
        allow_project_root: bool = False
    ):
        """
        Args:
            db_url: データベース URL
            versions_dir: マイグレーションファイルの保存場所
            version_table: Alembic バージョンテーブル名
            version_table_schema: Alembic バージョンテーブルのスキーマ（SQLite では無視）
            project_dirs: 削除対象にしないディレクトリ（alembic.ini の配置先など）。
                          config.root_path とカレントディレクトリは常に対象外
            allow_project_root: True の場合、project_dirs / config.root_path /
                                カレントディレクトリと一致する versions ディレクトリを許可
                                （シンボリックリンクは常に拒否）
        """
        self.db_url = db_url
        self.versions_dir = Path(versions_dir)
        self.version_table = version_table
        self.version_table_schema = version_table_schema
        self.project_dirs = [Path(project_dir) for project_dir in project_dirs]
        self.allow_project_root = allow_project_root

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

    def validate_versions_dir(self, versions_dir: Path) -> None:
        """versions ディレクトリが削除対象として安全か検証（削除はしない）

        Raises:
            UnsafeVersionsDirectoryError: シンボリックリンク、または
                project_dirs / config.root_path / カレントディレクトリと同じ場合
        """
        versions_dir = Path(versions_dir)
        if _is_link(versions_dir):
            raise UnsafeVersionsDirectoryError(
                f"Refusing to delete migration files through a linked "
                f"versions directory: {versions_dir}"
            )
        if not self.allow_project_root and is_project_directory(
            versions_dir, [*self.project_dirs, Path.cwd()]
        ):
            raise UnsafeVersionsDirectoryError(
                f"Refusing to delete migration files from the project or "
                f"working directory: {versions_dir}"
            )

    def delete_migration_files(self, versions_dir: Path | None = None) -> None:
        """マイグレーションファイルを削除

        Args:
            versions_dir: 削除対象のディレクトリ（省略時は self.versions_dir）

        Raises:
            UnsafeVersionsDirectoryError: validate_versions_dir() が拒否した場合
        """
        versions_dir = (
            Path(versions_dir) if versions_dir is not None else self.versions_dir
        )
        self.validate_versions_dir(versions_dir)
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
        if _is_link(pycache):
            print(f"[WARN] Skipped linked __pycache__: {pycache}")
        elif pycache.exists():
            import shutil
            shutil.rmtree(pycache)
            print("[OK] Deleted __pycache__")
