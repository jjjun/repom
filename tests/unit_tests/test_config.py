"""Tests for :mod:`repom.config`."""

from __future__ import annotations
from repom.config import RepomConfig
import pytest

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))


@pytest.fixture()
def config_factory(tmp_path):
    """Create a ``RepomConfig`` bound to a temporary root path."""

    def _factory(*, exec_env: str = "dev") -> RepomConfig:
        return RepomConfig(root_path=str(tmp_path), exec_env=exec_env)

    return _factory


def test_db_path_defaults_to_data_path(config_factory, tmp_path):
    """``db_path`` falls back to ``data_path`` and remains assignable."""

    config = config_factory()

    expected_default = Path(tmp_path) / "data" / "repom"
    assert config.db_path == str(expected_default)

    override = tmp_path / "custom_db"
    config.db_path = str(override)
    assert config.db_path == str(override)


@pytest.mark.parametrize(
    ("exec_env", "expected"),
    [
        ("test", "db.test.sqlite3"),
        ("dev", "db.dev.sqlite3"),
        ("prod", "db.sqlite3"),
    ],
)
def test_db_file_defaults_follow_exec_env(config_factory, exec_env, expected):
    """``db_file`` derives from ``exec_env`` for supported environments."""

    config = config_factory(exec_env=exec_env)

    assert config.db_file == expected


def test_db_file_is_overridable(config_factory):
    """``db_file`` can be explicitly set."""

    config = config_factory()

    config.db_file = "custom.sqlite3"
    assert config.db_file == "custom.sqlite3"


def test_db_file_path_combines_path_and_file(config_factory, tmp_path):
    """``db_file_path`` joins the resolved ``db_path`` and ``db_file``."""

    config = config_factory()
    default_expected = Path(config.db_path) / config.db_file
    assert config.db_file_path == str(default_expected)

    override_path = tmp_path / "overridden"
    override_file = "custom.sqlite3"
    config.db_path = str(override_path)
    config.db_file = override_file
    assert config.db_file_path == str(override_path / override_file)


def test_db_url_defaults_to_sqlite_uri(config_factory):
    """``db_url`` mirrors the SQLite connection string by default."""

    config = config_factory()

    expected = f"sqlite:///{config.db_path}/{config.db_file}"
    assert config.db_url == expected

    override = "sqlite:////tmp/custom.sqlite3"
    config.db_url = override
    assert config.db_url == override


def test_db_backup_path_defaults_to_backups_dir(config_factory, tmp_path):
    """``db_backup_path`` defaults to ``data_path / 'backups'`` and is overridable."""

    config = config_factory()

    expected_default = Path(config.data_path) / "backups"
    assert config.db_backup_path == str(expected_default)

    override = tmp_path / "custom_backups"
    config.db_backup_path = str(override)
    assert config.db_backup_path == str(override)
