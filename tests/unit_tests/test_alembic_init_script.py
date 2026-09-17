"""Tests for the alembic_init console script (repom#160).

alembic_init must read version_locations from an existing alembic.ini
instead of falling back to AlembicSetup's built-in defaults.
"""

from tests._init import *

from unittest.mock import MagicMock

from repom.alembic import AlembicTemplates
from repom.scripts import alembic_init


def _mock_config(root_path, db_url="sqlite:///data/repom_dev.sqlite3"):
    config = MagicMock()
    config.root_path = root_path
    config.db_url = db_url
    return config


def test_alembic_init_creates_default_layout_when_ini_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(alembic_init, "config", _mock_config(str(tmp_path)))

    alembic_init.main()

    assert (tmp_path / "alembic.ini").exists()
    versions_dir = tmp_path / "alembic" / "versions"
    assert (versions_dir / "__init__.py").exists()


def test_alembic_init_uses_existing_ini_version_locations(monkeypatch, tmp_path):
    """repom#160: an existing alembic.ini with a custom version_locations
    must not be ignored in favor of AlembicSetup's built-in defaults.
    """
    (tmp_path / "alembic.ini").write_text(AlembicTemplates.generate_alembic_ini(
        script_location="alembic",
        version_locations="%(here)s/migrations_ns2",
        version_table="alembic_version_ns2",
    ))

    monkeypatch.setattr(alembic_init, "config", _mock_config(str(tmp_path)))

    alembic_init.main()

    versions_dir = tmp_path / "migrations_ns2"
    assert (versions_dir / "__init__.py").exists()
    assert not (tmp_path / "alembic" / "versions").exists()
