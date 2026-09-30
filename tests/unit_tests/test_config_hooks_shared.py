import pytest

import repom.config_hooks as config_hooks
import repom.config_hook as repom_config_hook
from repom.config import RepomConfig
from repom.config_hooks import _parsing, parsing


def test_apply_repom_env_overrides_applies_helpers_in_canonical_order(monkeypatch):
    calls = []
    appliers = (
        "apply_database_env_overrides",
        "apply_postgres_env_overrides",
        "apply_pgadmin_env_overrides",
        "apply_redis_env_overrides",
        "apply_sqlite_env_overrides",
    )

    for name in appliers:
        monkeypatch.setattr(
            config_hooks,
            name,
            lambda config, name=name: calls.append((name, config)),
        )

    config = object()
    config_hooks.apply_repom_env_overrides(config)

    assert calls == [(name, config) for name in appliers]
    assert config_hooks.__all__ == ["apply_repom_env_overrides"]


def test_repom_config_hook_uses_shared_env_override_entry_point(monkeypatch):
    calls = []
    monkeypatch.setattr(repom_config_hook, "apply_repom_env_overrides", calls.append)
    config = RepomConfig()

    result = repom_config_hook.hook_config(config)

    assert result is config
    assert calls == [config]


def test_private_parsing_module_reexports_public_helpers():
    assert _parsing.TRUE_VALUES is parsing.TRUE_VALUES
    assert _parsing.FALSE_VALUES is parsing.FALSE_VALUES
    assert _parsing.parse_bool_env is parsing.parse_bool_env
    assert _parsing.parse_float_env is parsing.parse_float_env
    assert _parsing.parse_int_env is parsing.parse_int_env
    assert _parsing.parse_port_env is parsing.parse_port_env
    assert _parsing.parse_positive_int_env is parsing.parse_positive_int_env


@pytest.mark.parametrize(
    ("value", "expected"),
    [(" true ", True), ("YES", True), ("0", False), ("off", False)],
)
def test_parse_bool_env(value, expected):
    assert parsing.parse_bool_env("SETTING", value) is expected


def test_parse_bool_env_rejects_invalid_value():
    with pytest.raises(ValueError, match="SETTING must be a boolean value"):
        parsing.parse_bool_env("SETTING", "sometimes")


def test_parse_int_env_parses_and_rejects_invalid_value():
    assert parsing.parse_int_env("SETTING", "-2") == -2

    with pytest.raises(ValueError, match="SETTING must be an integer"):
        parsing.parse_int_env("SETTING", "invalid")


def test_parse_positive_int_env_parses_and_rejects_non_positive_values():
    assert parsing.parse_positive_int_env("SETTING", "2") == 2

    for value in ("0", "-1"):
        with pytest.raises(ValueError, match="SETTING must be a positive integer"):
            parsing.parse_positive_int_env("SETTING", value)

    with pytest.raises(ValueError, match="SETTING must be an integer"):
        parsing.parse_positive_int_env("SETTING", "invalid")


def test_parse_float_env_parses_and_rejects_invalid_value():
    assert parsing.parse_float_env("SETTING", "1.25") == 1.25

    with pytest.raises(ValueError, match="SETTING must be a float"):
        parsing.parse_float_env("SETTING", "invalid")


@pytest.mark.parametrize(("value", "expected"), [("1", 1), ("65535", 65535)])
def test_parse_port_env(value, expected):
    assert parsing.parse_port_env("PORT", value) == expected


@pytest.mark.parametrize("value", ["0", "65536"])
def test_parse_port_env_rejects_out_of_range_values(value):
    with pytest.raises(ValueError, match="PORT must be between 1 and 65535"):
        parsing.parse_port_env("PORT", value)


def test_parse_port_env_rejects_non_integer_value():
    with pytest.raises(ValueError, match="PORT must be an integer"):
        parsing.parse_port_env("PORT", "invalid")
