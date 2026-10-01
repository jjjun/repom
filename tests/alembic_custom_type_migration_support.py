"""Helpers for end-to-end custom-type Alembic migration tests."""

import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_custom_type_migration(
    tmp_path: Path,
    *,
    database_url: str,
    db_type: str,
) -> str:
    """Generate and run a custom-type revision in an isolated project."""
    test_root = tmp_path / "custom-type-migration-project"
    versions_dir = test_root / "alembic" / "versions"
    versions_dir.mkdir(parents=True)

    unique_id = uuid4().hex[:12]
    table_name = f"autogen_custom_types_{unique_id}"
    version_table = f"alembic_version_custom_types_{unique_id}"
    migration_database_url = database_url
    postgres_schema = None
    if db_type == "postgres":
        postgres_schema = f"repom_custom_types_{unique_id}"
        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(CreateSchema(postgres_schema))
        finally:
            engine.dispose()

        url = make_url(database_url)
        query = dict(url.query)
        existing_options = query.get("options", "")
        if isinstance(existing_options, tuple):
            existing_options = " ".join(existing_options)
        query["options"] = " ".join(
            filter(None, (existing_options, f"-csearch_path={postgres_schema}"))
        )
        migration_database_url = url.set(query=query).render_as_string(
            hide_password=False
        )

    model_package = test_root / "custom_type_migration"
    model_package.mkdir()
    (model_package / "__init__.py").write_text("", encoding="utf-8")
    (model_package / "models.py").write_text(
        f"""
from datetime import datetime

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from repom.database import Base
from repom.custom_types.ListJSON import ListJSON
from repom.custom_types.UTCDateTime import UTCDateTime


class CustomTypeMigrationModel(Base):
    __tablename__ = {table_name!r}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    tags: Mapped[list | None] = mapped_column(ListJSON(), nullable=True)
""".lstrip(),
        encoding="utf-8",
    )
    (test_root / "custom_type_migration_config.py").write_text(
        """
import os


def configure_database(config):
    config.root_path = os.environ["CUSTOM_TYPE_MIGRATION_ROOT"]
    config.db_url = os.environ["CUSTOM_TYPE_MIGRATION_DATABASE_URL"]
    config.model_locations = ["custom_type_migration"]
    config.allowed_package_prefixes = {
        "custom_type_migration",
        "custom_type_migration.",
        "repom.",
    }
    return config
""".lstrip(),
        encoding="utf-8",
    )

    alembic_ini = (PROJECT_ROOT / "alembic.ini").read_text(encoding="utf-8")
    alembic_ini = alembic_ini.replace(
        "script_location = alembic",
        f"script_location = {PROJECT_ROOT / 'alembic'}",
        1,
    )
    alembic_ini = alembic_ini.replace(
        "version_locations = alembic/versions",
        "version_locations = %(here)s/alembic/versions",
        1,
    )
    alembic_ini = alembic_ini.replace(
        "[alembic]\n",
        f"[alembic]\nversion_table = {version_table}\n",
        1,
    )
    config_path = test_root / "alembic.ini"
    config_path.write_text(alembic_ini, encoding="utf-8")

    env = os.environ.copy()
    env["EXEC_ENV"] = "test"
    env["DB_TYPE"] = db_type
    env["CONFIG_HOOK"] = "custom_type_migration_config:configure_database"
    env["CUSTOM_TYPE_MIGRATION_ROOT"] = str(test_root)
    env["CUSTOM_TYPE_MIGRATION_DATABASE_URL"] = migration_database_url
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(test_root), env.get("PYTHONPATH")))
    )
    alembic_command = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(config_path),
    ]

    try:
        revision_result = subprocess.run(
            [
                *alembic_command,
                "revision",
                "--autogenerate",
                "-m",
                "custom types",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )
        assert revision_result.returncode == 0, (
            "alembic revision --autogenerate failed:\n"
            f"{revision_result.stderr}\n{revision_result.stdout}"
        )

        generated_revisions = list(versions_dir.glob("*.py"))
        assert len(generated_revisions) == 1
        revision_path = generated_revisions[0]
        revision_source = revision_path.read_text(encoding="utf-8")
        assert "import repom.custom_types.UTCDateTime" in revision_source
        assert "import repom.custom_types.ListJSON" in revision_source

        for command in (("upgrade", "head"), ("downgrade", "base")):
            result = subprocess.run(
                [*alembic_command, *command],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=45,
                env=env,
            )
            assert result.returncode == 0, (
                f"alembic {' '.join(command)} failed:\n{result.stderr}\n"
                f"{result.stdout}"
            )

        return revision_source
    finally:
        if postgres_schema is not None:
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(
                        DropSchema(postgres_schema, cascade=True, if_exists=True)
                    )
            finally:
                engine.dispose()
