from types import SimpleNamespace

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
