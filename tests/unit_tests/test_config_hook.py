from repom._.config_hook import Config, get_config_from_hook


def test_get_config_from_hook_returns_config_when_module_missing(monkeypatch, capsys):
    monkeypatch.setenv("CONFIG_HOOK", "missing_package.config:hook_config")
    config = Config()

    result = get_config_from_hook(config)

    assert result is config
    assert "Failed to import hook module" in capsys.readouterr().out


def test_get_config_from_hook_returns_config_when_function_missing(monkeypatch, capsys):
    monkeypatch.setenv("CONFIG_HOOK", "repom.config_hook:missing_hook")
    config = Config()

    result = get_config_from_hook(config)

    assert result is config
    assert "Function 'missing_hook' not found" in capsys.readouterr().out
