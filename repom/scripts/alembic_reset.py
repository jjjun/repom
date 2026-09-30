"""Alembic マイグレーションのリセットスクリプト

alembic.ini から設定を取得して AlembicSetup を実行。
alembic.ini がマイグレーションの配置場所の唯一の情報源であるため、
project_root からデフォルトを組み立てず、指定された ini ファイルを読む。
"""
import argparse
from pathlib import Path

from repom.alembic.setup import AlembicSetup
from repom.config import config
from repom.database import safe_db_url
from repom.scripts._destructive import confirm_destructive_operation


def _resolve_alembic_reset(
    config_path: str | Path | None = None,
) -> tuple[AlembicSetup, str]:
    ini_path = (
        Path(config_path) if config_path
        else Path(config.root_path) / "alembic.ini"
    )
    if not ini_path.is_file():
        raise FileNotFoundError(f"Alembic config file not found: {ini_path}")

    setup = AlembicSetup.from_ini(ini_path, config.db_url)

    version_table_display = setup.version_table or "alembic_version"
    if setup.version_table_schema:
        version_table_display = (
            f"{setup.version_table_schema}.{version_table_display}"
        )
    versions_dirs_display = ", ".join(
        str(versions_dir) for versions_dir in setup.versions_dirs
    )
    target = (
        f"{safe_db_url(config.db_url)} "
        f"(version table: {version_table_display}; "
        f"version directories: {versions_dirs_display})"
    )
    return setup, target


def describe_alembic_reset(config_path: str | Path | None = None) -> str:
    """Return reset targets, raising FileNotFoundError if the ini is missing."""
    _, target = _resolve_alembic_reset(config_path)
    return target


def reset_alembic_migrations(
    *, config_path: str | Path | None = None, yes: bool = False
) -> None:
    """Confirm and reset an ini, raising FileNotFoundError if it is missing."""
    setup, target = _resolve_alembic_reset(config_path)
    confirm_destructive_operation(
        operation="reset Alembic migrations",
        target=target,
        exec_env=config.exec_env,
        yes=yes,
    )

    print("Resetting Alembic migrations...")
    setup.reset_migrations()
    print("[OK] Alembic migrations reset successfully")


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Drop the Alembic version table and delete migration files."
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Confirm non-interactively; required when stdin is not a TTY (a TTY still prompts).",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to the alembic.ini to reset (default: <root_path>/alembic.ini).",
    )
    args = parser.parse_args(argv)
    try:
        reset_alembic_migrations(config_path=args.config, yes=args.yes)
    except FileNotFoundError as exc:
        print(exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
