"""Alembic setup and management utilities."""

from pathlib import Path
from alembic.config import Config as AlembicConfig
from repom.alembic.templates import AlembicTemplates
from repom.alembic.reset import AlembicReset


class AlembicSetup:
    """Alembic セットアップと管理のための統合ユーティリティ

    テストとスクリプトの両方で使用可能。
    config に依存せず、引数でパスを受け取る設計。
    """

    def __init__(
        self,
        project_root: str | Path,
        db_url: str,
        script_location: str = "alembic",
        version_locations: str = "%(here)s/alembic/versions"
    ):
        """
        Args:
            project_root: プロジェクトルートディレクトリ（alembic.ini を配置する場所）
            db_url: データベース URL（必須）
            script_location: repom の alembic への相対パス（プロジェクトルートから）
                           repom standalone: 'alembic'
                           外部プロジェクト: 'submod/fast-domain/submod/repom/alembic'
                           （デフォルト: 'alembic'）
            version_locations: マイグレーションファイルの保存場所
                             %(here)s は alembic.ini の場所（プロジェクトルート）を指す
                             例: '%(here)s/alembic/versions'
                             （デフォルト: '%(here)s/alembic/versions'）

        Note:
            - db_url や各パスのデフォルト値は scripts/ 側で config から取得して渡す
            - %(here)s により、alembic.ini の配置場所に依存しない相対パス指定が可能
            - script_location: env.py を含む repom の alembic ディレクトリへのパス
        """
        self.project_root = Path(project_root)
        self.db_url = db_url
        self.script_location = script_location
        self.version_locations = version_locations

        self.alembic_dir = self.project_root / self.script_location
        # %(here)s が含まれている場合は実際のパスに展開
        versions_path = version_locations.replace('%(here)s', str(self.project_root))
        self.versions_dir = Path(versions_path)

    def create_alembic_ini(self, overwrite: bool = False) -> None:
        """alembic.ini を生成

        Args:
            overwrite: 既存ファイルを上書きするか（デフォルト: False）

        Note:
            env.py と script.py.mako は repom が提供するため、生成しません。
        """
        ini_path = self.project_root / "alembic.ini"

        # 既存ファイルがある場合は上書きしない（安全）
        if ini_path.exists() and not overwrite:
            print(f"[OK] alembic.ini already exists: {ini_path}")
            return

        content = AlembicTemplates.generate_alembic_ini(
            script_location=self.script_location,
            version_locations=self.version_locations
        )
        ini_path.write_text(content, encoding='utf-8')
        print(f"[OK] Created alembic.ini: {ini_path}")

    def create_version_directory(self) -> None:
        """version_locations ディレクトリを作成"""
        if self.versions_dir.exists():
            print(f"[OK] Version directory already exists: {self.versions_dir}")
            return

        self.versions_dir.mkdir(parents=True, exist_ok=True)

        # __init__.py を作成（Python パッケージとして認識させる）
        init_file = self.versions_dir / "__init__.py"
        init_file.touch()
        print(f"[OK] Created version directory: {self.versions_dir}")

    def reset_migrations(
        self,
        drop_table: bool = True,
        delete_files: bool = True
    ) -> None:
        """マイグレーションをリセット

        Args:
            drop_table: alembic_version テーブルを削除するか
            delete_files: マイグレーションファイルを削除するか
        """
        reset = AlembicReset(
            db_url=self.db_url,
            versions_dir=self.versions_dir
        )

        if drop_table:
            reset.drop_alembic_version_table()

        if delete_files:
            reset.delete_migration_files()

    def get_alembic_config(self) -> AlembicConfig:
        """Alembic Config オブジェクトを取得"""
        ini_path = self.project_root / "alembic.ini"
        if not ini_path.exists():
            raise FileNotFoundError(
                f"alembic.ini not found at {ini_path}. "
                f"Run create_alembic_ini() first."
            )

        config = AlembicConfig(str(ini_path))
        config.set_main_option("sqlalchemy.url", self.db_url)
        return config
