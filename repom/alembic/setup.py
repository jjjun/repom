"""Alembic setup and management utilities."""

from collections.abc import Sequence
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
        version_locations: str = "%(here)s/alembic/versions",
        version_table: str | None = None,
        autogenerate_exclude_tables: str | Sequence[str] | None = None,
        version_table_schema: str | None = None
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
            version_table: Alembic version table name
            autogenerate_exclude_tables: Sibling version table names to exclude
            version_table_schema: Alembic version table schema

        Note:
            - db_url や各パスのデフォルト値は scripts/ 側で config から取得して渡す
            - %(here)s により、alembic.ini の配置場所に依存しない相対パス指定が可能
            - script_location: env.py を含む repom の alembic ディレクトリへのパス
        """
        self.project_root = Path(project_root)
        self.db_url = db_url
        self.script_location = script_location
        self.version_locations = version_locations
        self.version_table = version_table
        self.version_table_schema = version_table_schema
        self.autogenerate_exclude_tables = autogenerate_exclude_tables

        # %(here)s が含まれている場合は実際のパスに展開
        versions_path = version_locations.replace('%(here)s', str(self.project_root))
        self.versions_dir = Path(versions_path)
        self.versions_dirs = [self.versions_dir]

    @classmethod
    def from_ini(cls, ini_path: str | Path, db_url: str) -> "AlembicSetup":
        """既存の alembic.ini から AlembicSetup を構築

        Args:
            ini_path: 読み込む alembic.ini のパス
            db_url: データベース URL（alembic.ini からは読み込まない）

        Note:
            script_location, version_locations, version_table,
            version_table_schema は alembic.config.Config 経由で読み込むため、
            %(here)s の展開と、path_separator（非推奨の version_path_separator
            を含む）による version_locations の分割は、alembic 本体
            （alembic upgrade / alembic revision）と同じ規則に従う。
            %(here)s を使わない相対パスは、alembic.ini の配置ディレクトリを
            基準に解決する。
        """
        ini_path = Path(ini_path)
        here = ini_path.resolve().parent
        alembic_config = AlembicConfig(str(ini_path))

        script_location = alembic_config.get_main_option(
            "script_location", "alembic"
        )
        version_table = alembic_config.get_main_option(
            "version_table", "alembic_version"
        )
        version_table_schema = alembic_config.get_main_option(
            "version_table_schema"
        )
        if version_table_schema is not None:
            version_table_schema = version_table_schema.strip() or None

        def _resolve(raw_location: str) -> Path:
            location = Path(raw_location)
            return location if location.is_absolute() else here / location

        raw_version_locations = alembic_config.get_version_locations_list()
        if raw_version_locations:
            versions_dirs = [_resolve(raw) for raw in raw_version_locations]
            version_locations = raw_version_locations[0]
        else:
            # Matches alembic.script.ScriptDirectory.from_config: when
            # version_locations is absent, Alembic itself falls back to
            # "<script_location>/versions", not a hard-coded "alembic/versions".
            default_versions_dir = _resolve(script_location) / "versions"
            versions_dirs = [default_versions_dir]
            version_locations = default_versions_dir.as_posix()

        setup = cls(
            project_root=here,
            db_url=db_url,
            script_location=script_location,
            version_locations=version_locations,
            version_table=version_table,
            version_table_schema=version_table_schema
        )
        setup.versions_dir = versions_dirs[0]
        setup.versions_dirs = versions_dirs
        return setup

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
            version_locations=self.version_locations,
            version_table=self.version_table,
            version_table_schema=self.version_table_schema,
            autogenerate_exclude_tables=self.autogenerate_exclude_tables
        )
        ini_path.write_text(content, encoding='utf-8')
        print(f"[OK] Created alembic.ini: {ini_path}")

    def create_version_directory(self) -> None:
        """version_locations の各ディレクトリを作成"""
        for versions_dir in self.versions_dirs:
            if versions_dir.exists():
                print(f"[OK] Version directory already exists: {versions_dir}")
                continue

            versions_dir.mkdir(parents=True, exist_ok=True)

            # __init__.py を作成（Python パッケージとして認識させる）
            init_file = versions_dir / "__init__.py"
            init_file.touch()
            print(f"[OK] Created version directory: {versions_dir}")

    def reset_migrations(
        self,
        drop_table: bool = True,
        delete_files: bool = True
    ) -> None:
        """マイグレーションをリセット

        Args:
            drop_table: 設定された Alembic バージョンテーブルを削除するか
            delete_files: マイグレーションファイルを削除するか

        Note:
            設定されたバージョンテーブルが存在しない場合、テーブル削除は何もせず、
            delete_files が True ならマイグレーションファイルの削除は続行します。
            version_table の指定を誤ると、データベースにリビジョンが記録されたまま、
            対応するスクリプトが削除されます。
            version_locations が複数のディレクトリを指す場合、delete_files は
            そのすべてを対象にします。
        """
        reset = AlembicReset(
            db_url=self.db_url,
            versions_dir=self.versions_dir,
            version_table=self.version_table or "alembic_version",
            version_table_schema=self.version_table_schema
        )

        # A missing version table remains a reported no-op for compatibility;
        # explicitly requested migration-file deletion still proceeds.
        if drop_table:
            reset.drop_alembic_version_table()

        if delete_files:
            for versions_dir in self.versions_dirs:
                reset.delete_migration_files(versions_dir)

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
