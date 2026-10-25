"""Alembic setup and management utilities."""

from collections.abc import Sequence
from pathlib import Path
from alembic.config import Config as AlembicConfig
from alembic.util.pyfiles import coerce_resource_to_filename
from repom.alembic.constants import SCRIPT_LOCATION
from repom.alembic.options import resolve_version_table_options
from repom.alembic.templates import AlembicTemplates
from repom.alembic.reset import AlembicReset, is_project_directory
from repom.exceptions import UnsafeVersionsDirectoryError


class AlembicSetup:
    """Alembic セットアップと管理のための統合ユーティリティ

    テストとスクリプトの両方で使用可能。
    config に依存せず、引数でパスを受け取る設計。
    """

    def __init__(
        self,
        project_root: str | Path,
        db_url: str,
        script_location: str = SCRIPT_LOCATION,
        version_locations: str = "%(here)s/alembic/versions",
        version_table: str | None = None,
        autogenerate_exclude_tables: str | Sequence[str] | None = None,
        version_table_schema: str | None = None,
        allow_project_root: bool = False
    ):
        """
        Args:
            project_root: プロジェクトルートディレクトリ（alembic.ini を配置する場所）
            db_url: データベース URL（必須）
            script_location: repom の alembic 環境への指定
                           （デフォルト: 'repom:alembic'）
            version_locations: マイグレーションファイルの保存場所
                             %(here)s は alembic.ini の場所（プロジェクトルート）を指す
                             例: '%(here)s/alembic/versions'
                             （デフォルト: '%(here)s/alembic/versions'）
            version_table: Alembic version table name
            autogenerate_exclude_tables: Sibling version table names to exclude
            version_table_schema: Alembic version table schema
            allow_project_root: True の場合、reset_migrations() が project_root /
                              config.root_path / カレントディレクトリと一致する
                              versions ディレクトリを削除対象にすることを許可

        Note:
            - db_url や各パスのデフォルト値は scripts/ 側で config から取得して渡す
            - %(here)s により、alembic.ini の配置場所に依存しない相対パス指定が可能
            - script_location: repom の alembic 環境への指定
        """
        self.project_root = Path(project_root)
        self.db_url = db_url
        self.script_location = script_location
        self.version_locations = version_locations
        self.version_table = version_table
        self.version_table_schema = version_table_schema
        self.autogenerate_exclude_tables = autogenerate_exclude_tables
        self.allow_project_root = allow_project_root

        # %(here)s が含まれている場合は実際のパスに展開
        versions_path = version_locations.replace('%(here)s', str(self.project_root))
        self.versions_dir = Path(versions_path)
        self.versions_dirs = [self.versions_dir]

    @classmethod
    def from_ini(
        cls,
        ini_path: str | Path,
        db_url: str,
        *,
        allow_project_root: bool = False
    ) -> "AlembicSetup":
        """既存の alembic.ini から AlembicSetup を構築

        Args:
            ini_path: 読み込む alembic.ini のパス
            db_url: データベース URL（alembic.ini からは読み込まない）
            allow_project_root: True の場合、alembic.ini のディレクトリや
                              config.root_path と一致する version_locations を許可

        Raises:
            UnsafeVersionsDirectoryError: version_locations の項目が
                alembic.ini のディレクトリまたは config.root_path と一致し、
                allow_project_root が False の場合

        Note:
            script_location, version_locations, version_table,
            version_table_schema は alembic.config.Config 経由で読み込むため、
            %(here)s の展開と、path_separator（非推奨の version_path_separator
            を含む）による version_locations の分割は、alembic 本体
            （alembic upgrade / alembic revision）と同じ規則に従う。
            %(here)s を使わない相対パスは、alembic.ini の配置ディレクトリを
            基準に解決する（alembic 本体はカレントディレクトリ基準のため、
            alembic.ini の場所に依存させるには %(here)s を使う）。
            空白のみの項目は無視する。
            version_table が空または空白のみの場合は未指定と同様に
            alembic_version、version_table_schema は None として扱う。
        """
        ini_path = Path(ini_path)
        here = ini_path.resolve().parent
        alembic_config = AlembicConfig(str(ini_path))

        script_location = alembic_config.get_main_option(
            "script_location", SCRIPT_LOCATION
        )
        version_table, version_table_schema = resolve_version_table_options(
            alembic_config
        )

        def _resolve(raw_location: str) -> Path:
            location = Path(raw_location)
            return location if location.is_absolute() else here / location

        # Alembic's splitter keeps whitespace-only tokens as "", which
        # Path("") would resolve to the ini directory itself.
        raw_version_locations = [
            raw
            for raw in alembic_config.get_version_locations_list() or []
            if raw.strip()
        ]
        if raw_version_locations:
            versions_dirs = [_resolve(raw) for raw in raw_version_locations]
            version_locations = raw_version_locations[0]
        else:
            # Matches alembic.script.ScriptDirectory.from_config: when
            # version_locations is absent, Alembic itself falls back to
            # "<script_location>/versions", not a hard-coded "alembic/versions".
            script_path = (
                Path(coerce_resource_to_filename(script_location))
                if ":" in script_location
                and not Path(script_location).is_absolute()
                else _resolve(script_location)
            )
            default_versions_dir = script_path / "versions"
            versions_dirs = [default_versions_dir]
            version_locations = default_versions_dir.as_posix()

        if not allow_project_root:
            for versions_dir in versions_dirs:
                if is_project_directory(versions_dir, [here]):
                    raise UnsafeVersionsDirectoryError(
                        f"version_locations entry resolves to the project "
                        f"directory, not a versions directory: {versions_dir}"
                    )

        setup = cls(
            project_root=here,
            db_url=db_url,
            script_location=script_location,
            version_locations=version_locations,
            version_table=version_table,
            version_table_schema=version_table_schema,
            allow_project_root=allow_project_root
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
            versions ディレクトリが project_root / config.root_path /
            カレントディレクトリと一致する場合、またはシンボリックリンクの場合は
            UnsafeVersionsDirectoryError を送出し、何も削除しません
            （allow_project_root=True で一致のみ許可）。
        """
        reset = AlembicReset(
            db_url=self.db_url,
            versions_dir=self.versions_dir,
            version_table=self.version_table or "alembic_version",
            version_table_schema=self.version_table_schema,
            project_dirs=[self.project_root],
            allow_project_root=self.allow_project_root
        )

        # Refuse before dropping the version table so a refused directory
        # cannot leave the reset half done.
        if delete_files:
            for versions_dir in self.versions_dirs:
                reset.validate_versions_dir(versions_dir)

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
        config.set_main_option("sqlalchemy.url", self.db_url.replace("%", "%%"))
        return config
