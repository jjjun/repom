import pytest

from basekit.config_hook import (
    Config,
    ConfigHookLoadError,
    get_config_from_hook,
)


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
