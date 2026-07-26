"""Alembic configuration file templates."""

from collections.abc import Sequence


class AlembicTemplates:
    """Alembic 設定ファイルのテンプレート提供"""

    @staticmethod
    def generate_alembic_ini(
        script_location: str,
        version_locations: str,
        version_table: str | None = None,
        autogenerate_exclude_tables: str | Sequence[str] | None = None
    ) -> str:
        """alembic.ini を生成

        Args:
            script_location: repom が提供する alembic への相対パス（プロジェクトルートから）
                           repom standalone: 'alembic'
                           外部プロジェクト: 'submod/fast-domain/submod/repom/alembic'
            version_locations: マイグレーションファイルの保存場所
                             %(here)s は alembic.ini の場所（プロジェクトルート）を指す
                             例: '%(here)s/alembic/versions'
                                'alembic/versions' の部分を変数で埋め込む
            version_table: Alembic version table name
            autogenerate_exclude_tables: Sibling version table names to exclude

        Note:
            - script_location: env.py と script.py.mako を含む repom の alembic ディレクトリ
            - version_locations: %(here)s + マイグレーションディレクトリのパス
            - %(here)s により、alembic.ini の配置場所に依存しない相対パス指定が可能
        """
        version_table_option = (
            f"version_table = {version_table}\n\n"
            if version_table is not None
            else (
                "# Optional: isolate an independent migration namespace.\n"
                "# Defaults to alembic_version when omitted.\n"
                "# version_table = alembic_version_fast_domain\n\n"
            )
        )
        if not autogenerate_exclude_tables:
            exclude_tables_option = (
                "# autogenerate_exclude_tables = alembic_version_fast_domain"
            )
        elif isinstance(autogenerate_exclude_tables, str):
            exclude_tables_option = (
                f"autogenerate_exclude_tables = "
                f"{autogenerate_exclude_tables}"
            )
        else:
            exclude_tables_option = (
                "autogenerate_exclude_tables = "
                f"{', '.join(autogenerate_exclude_tables)}"
            )

        return f"""# Alembic configuration
# Uses repom's env.py for migration execution

[alembic]
# Path to migration scripts (uses repom's env.py)
# This should point to repom's alembic directory from project root
script_location = {script_location}

# Location where migration files are stored
# %(here)s refers to the directory containing this alembic.ini (project root)
version_locations = {version_locations}

{version_table_option}# Comma-separated sibling migration version tables to ignore during autogenerate.
# Do not list the active version_table; Alembic excludes it automatically.
{exclude_tables_option}

# Path separator for version_locations (when multiple paths are specified)
# Using 'os' allows OS-specific path separators
path_separator = os

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
