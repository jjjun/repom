from types import SimpleNamespace

import pytest

import repom.config as config_module
from repom.config import RepomConfig
from repom.config_hook import hook_config


def test_hook_config_configures_repom_package(monkeypatch):
    monkeypatch.setenv("EXEC_ENV", "test")
    config = RepomConfig()
    config.package_name = "repom"

    result = hook_config(config)

    assert result is config
    assert config.model_locations == ["repom.examples.models"]
    assert config.db_type == "sqlite"


@pytest.mark.parametrize("exec_env", ["TEST", " test ", "Test"])
def test_hook_config_selects_sqlite_for_normalized_test_env(exec_env):
    config = RepomConfig(exec_env=exec_env)

    hook_config(config)

    assert config.exec_env == exec_env
    assert config.db_type == "sqlite"


def test_hook_config_uses_postgres_and_warns_for_unknown_exec_env(caplog):
    config = RepomConfig(exec_env="test-hook-unknown-environment")

    with caplog.at_level("WARNING", logger="repom.exec_env"):
        hook_config(config)

    assert config.exec_env == "test-hook-unknown-environment"
    assert config.db_type == "postgres"
    assert any("Unknown EXEC_ENV" in record.message for record in caplog.records)


def test_hook_config_only_sets_root_path_for_external_package():
    config = SimpleNamespace(package_name="external_app", root_path=None)

    result = hook_config(config)

    assert result is config
    assert config.root_path
    assert not hasattr(config, "model_locations")


def test_load_config_passes_repom_config_to_hook_loader(monkeypatch, tmp_path):
    config = RepomConfig(root_path=str(tmp_path))
    received = []

    def capture_config_hook(config):
        received.append(config)
        return config

    monkeypatch.setattr(config_module, "get_config_from_hook", capture_config_hook)

    result = config_module._load_config(config)

    assert result is config
    assert received == [config]
    assert isinstance(received[0], RepomConfig)
