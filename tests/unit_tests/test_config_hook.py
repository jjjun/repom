from types import SimpleNamespace

import pytest

from basekit.config_hook import (
    Config,
    ConfigHookLoadError,
    get_config_from_hook,
)
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


def test_get_config_from_hook_returns_config_when_hook_missing(monkeypatch):
    monkeypatch.delenv("CONFIG_HOOK", raising=False)
    config = Config()

    result = get_config_from_hook(config)

    assert result is config


def test_get_config_from_hook_raises_when_module_missing(monkeypatch):
    monkeypatch.setenv("CONFIG_HOOK", "missing_package.config:hook_config")
    config = Config()

    with pytest.raises(ConfigHookLoadError, match="Failed to import config hook module"):
        get_config_from_hook(config)


def test_get_config_from_hook_raises_when_function_missing(monkeypatch):
    monkeypatch.setenv("CONFIG_HOOK", "repom.config_hook:missing_hook")
    config = Config()

    with pytest.raises(ConfigHookLoadError, match="Config hook function 'missing_hook' was not found"):
        get_config_from_hook(config)


def test_get_config_from_hook_raises_when_target_is_not_callable(monkeypatch):
    monkeypatch.setenv("CONFIG_HOOK", "repom.config_hook:__doc__")
    config = Config()

    with pytest.raises(ConfigHookLoadError, match="is not callable"):
        get_config_from_hook(config)
