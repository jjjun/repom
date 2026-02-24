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
    assert config.sqlite.db_path == str(expected_default)

    override = tmp_path / "custom_db"
    config.sqlite.db_path = str(override)
    assert config.sqlite.db_path == str(override)


@pytest.mark.parametrize(
    ("exec_env", "expected"),
    [
        ("test", "repom_test.sqlite3"),
        ("dev", "repom_dev.sqlite3"),
        ("prod", "repom.sqlite3"),
    ],
)
def test_db_file_defaults_follow_exec_env(config_factory, exec_env, expected):
    """``db_file`` derives from ``exec_env`` for supported environments."""

    config = config_factory(exec_env=exec_env)

    assert config.sqlite.db_file == expected


def test_db_file_is_overridable(config_factory):
    """``db_file`` can be explicitly set."""

    config = config_factory()

    config.sqlite.db_file = "custom.sqlite3"
    assert config.sqlite.db_file == "custom.sqlite3"


def test_db_file_path_combines_path_and_file(config_factory, tmp_path):
    """``db_file_path`` joins the resolved ``db_path`` and ``db_file``."""

    config = config_factory()
    default_expected = Path(config.sqlite.db_path) / config.sqlite.db_file
    assert config.sqlite.db_file_path == str(default_expected)

    override_path = tmp_path / "overridden"
    override_file = "custom.sqlite3"
    config.sqlite.db_path = str(override_path)
    config.sqlite.db_file = override_file
    assert config.sqlite.db_file_path == str(override_path / override_file)


def test_db_url_defaults_to_sqlite_uri(config_factory):
    """``db_url`` mirrors the SQLite connection string by default."""

    config = config_factory()

    expected = f"sqlite:///{config.sqlite.db_path}/{config.sqlite.db_file}"
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


def test_use_in_memory_db_for_tests_defaults_to_true(config_factory):
    """``use_in_memory_db_for_tests`` defaults to True."""
    config = config_factory(exec_env="test")
    assert config.sqlite.use_in_memory_for_tests is True


def test_use_in_memory_db_for_tests_is_settable(config_factory):
    """``use_in_memory_db_for_tests`` can be explicitly set."""
    config = config_factory(exec_env="test")

    config.sqlite.use_in_memory_for_tests = False
    assert config.sqlite.use_in_memory_for_tests is False

    config.sqlite.use_in_memory_for_tests = True
    assert config.sqlite.use_in_memory_for_tests is True


def test_db_url_returns_in_memory_for_test_env(config_factory):
    """``db_url`` returns 'sqlite:///:memory:' when exec_env='test' and use_in_memory_db_for_tests=True."""
    config = config_factory(exec_env="test")

    # デフォルト（use_in_memory_db_for_tests=True）
    assert config.db_url == "sqlite:///:memory:"


def test_db_url_returns_file_based_when_in_memory_disabled(config_factory):
    """``db_url`` returns file-based URL when use_in_memory_db_for_tests=False."""
    config = config_factory(exec_env="test")

    config.sqlite.use_in_memory_for_tests = False
    expected = f"sqlite:///{config.sqlite.db_path}/{config.sqlite.db_file}"
    assert config.db_url == expected


def test_db_url_returns_file_based_for_non_test_env(config_factory):
    """``db_url`` returns file-based URL for non-test environments regardless of use_in_memory_db_for_tests."""
    # dev 環境
    config_dev = config_factory(exec_env="dev")
    assert config_dev.db_url == f"sqlite:///{config_dev.sqlite.db_path}/{config_dev.sqlite.db_file}"

    # prod 環境
    config_prod = config_factory(exec_env="prod")
    assert config_prod.db_url == f"sqlite:///{config_prod.sqlite.db_path}/{config_prod.sqlite.db_file}"


def test_db_url_override_takes_precedence(config_factory):
    """Explicitly set ``db_url`` takes precedence over in-memory logic."""
    config = config_factory(exec_env="test")

    custom_url = "sqlite:////tmp/custom.sqlite3"
    config.db_url = custom_url
    assert config.db_url == custom_url


# =============================================================================
# db_name tests
# =============================================================================


def test_db_name_default(config_factory):
    """``db_name`` defaults to 'repom'."""
    config = config_factory()
    assert config.db_name == "repom"


def test_db_name_is_settable(config_factory):
    """``db_name`` can be explicitly set."""
    config = config_factory()
    config.db_name = "myapp"
    assert config.db_name == "myapp"


def test_postgres_db_uses_db_name(config_factory):
    """``postgres_db`` uses ``db_name`` as base."""
    config = config_factory(exec_env="dev")
    config.db_name = "myapp"
    assert config.postgres_db == "myapp_dev"

    config_test = config_factory(exec_env="test")
    config_test.db_name = "myapp"
    assert config_test.postgres_db == "myapp_test"

    config_prod = config_factory(exec_env="prod")
    config_prod.db_name = "myapp"
    assert config_prod.postgres_db == "myapp"


def test_postgres_database_overrides_db_name(config_factory):
    """``postgres.database`` takes precedence over ``db_name``."""
    config = config_factory(exec_env="dev")
    config.db_name = "myapp"
    config.postgres.database = "custom_db"
    assert config.postgres_db == "custom_db"


def test_sqlite_db_file_uses_db_name(config_factory):
    """SQLite db_file uses ``db_name`` as prefix."""
    config = config_factory(exec_env="dev")
    config.db_name = "myapp"
    # Re-initialize to apply db_name to sqlite config
    config.sqlite.db_file = None
    config.sqlite.bind(config)
    expected_file = "myapp_dev.sqlite3"
    assert config.sqlite.get_default_db_file("dev") == expected_file


def test_sqlite_db_file_prod_uses_db_name(config_factory):
    """SQLite db_file for prod uses ``db_name`` without suffix."""
    config = config_factory(exec_env="prod")
    config.db_name = "myapp"
    config.sqlite.bind(config)
    expected_file = "myapp.sqlite3"
    assert config.sqlite.get_default_db_file("prod") == expected_file
