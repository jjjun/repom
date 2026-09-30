"""Tests for execution environment normalization."""

import logging

import pytest

import repom.exec_env as exec_env_module
from repom.exec_env import is_prod_exec_env, normalize_exec_env


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("dev", "dev"),
        (" DEV ", "dev"),
        ("test", "test"),
        (" Test ", "test"),
        ("prod", "prod"),
        ("production", "prod"),
        (" Production ", "prod"),
    ],
)
def test_normalize_exec_env_supported_values(value, expected):
    assert normalize_exec_env(value) == expected


@pytest.mark.parametrize("value", ["prod", "production", " Production "])
def test_is_prod_exec_env_accepts_production_aliases(value):
    assert is_prod_exec_env(value)


@pytest.mark.parametrize("value", ["dev", "test", "prdo", ""])
def test_is_prod_exec_env_rejects_other_values(value):
    assert not is_prod_exec_env(value)


@pytest.mark.parametrize("value", ["test-exec-env-195-unknown", ""])
def test_normalize_exec_env_warns_once_and_falls_back_to_dev(
    value, caplog, monkeypatch
):
    monkeypatch.setattr(exec_env_module, "_warned_unknown_exec_envs", set())

    with caplog.at_level(logging.WARNING, logger="repom.exec_env"):
        assert normalize_exec_env(value) == "dev"
        assert normalize_exec_env(value) == "dev"

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "Unknown EXEC_ENV" in warnings[0].message
    assert repr(value) in warnings[0].message
    assert "dev database defaults" in warnings[0].message


def test_normalize_exec_env_warns_once_for_each_distinct_unknown_value(
    caplog, monkeypatch
):
    values = ("test-exec-env-195-first", "test-exec-env-195-second")
    monkeypatch.setattr(exec_env_module, "_warned_unknown_exec_envs", set())

    with caplog.at_level(logging.WARNING, logger="repom.exec_env"):
        for value in values:
            assert normalize_exec_env(value) == "dev"

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == len(values)
    assert {record.args[0] for record in warnings} == set(values)
