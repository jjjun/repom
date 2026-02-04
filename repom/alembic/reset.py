"""Alembic migration reset functionality."""

from pathlib import Path
from sqlalchemy import create_engine, text


class AlembicReset:
    """Alembic マイグレーションのリセット機能"""
    
    def __init__(
        self,
        db_url: str,
        versions_dir: Path
    ):
        self.db_url = db_url
        self.versions_dir = Path(versions_dir)
    
    def drop_alembic_version_table(self) -> None:
        """alembic_version テーブルを削除"""
        engine = create_engine(self.db_url)
        
        with engine.connect() as conn:
            # テーブルが存在するか確認
            result = conn.execute(text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='alembic_version'"
            ))
            
            if result.fetchone():
                conn.execute(text("DROP TABLE alembic_version"))
                conn.commit()
                print("✓ Dropped alembic_version table")
            else:
                print("✓ alembic_version table does not exist")
    
    def delete_migration_files(self) -> None:
        """マイグレーションファイルを削除"""
        if not self.versions_dir.exists():
            print(f"✓ Versions directory does not exist: {self.versions_dir}")
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
            print(f"✓ Deleted {deleted_count} migration file(s)")
        else:
            print("✓ No migration files to delete")
        
        # __pycache__ も削除
        pycache = self.versions_dir / "__pycache__"
        if pycache.exists():
            import shutil
            shutil.rmtree(pycache)
            print("✓ Deleted __pycache__")
