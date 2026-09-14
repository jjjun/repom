"""Tests for Redis credential helpers."""

from io import StringIO
import sys
from unittest.mock import MagicMock, patch

import pytest

from repom.redis.credentials import (
    RedisCredentialRotationError,
    RedisCredentialRotationPlan,
    build_redis_cli_command,
    build_redis_ping_command,
    rotate_redis_password,
)
from repom.redis.manage import main_rotate_password, rotate_password


def test_redis_cli_command_without_env_file():
    command = build_redis_cli_command(container_name="repom_redis")

    assert command == ("docker", "exec", "-i", "repom_redis", "redis-cli")


def test_redis_cli_command_uses_env_file_when_given():
    command = build_redis_cli_command(
        container_name="repom_redis",
        env_file="/tmp/repom-redis-auth-xyz.env",
    )

    assert command == (
        "docker",
        "exec",
        "-i",
        "--env-file",
        "/tmp/repom-redis-auth-xyz.env",
        "repom_redis",
        "redis-cli",
    )


def test_redis_ping_command_appends_ping_and_never_carries_a_password():
    command = build_redis_ping_command(container_name="repom_redis")

    assert command[-1] == "ping"
    assert command == ("docker", "exec", "-i", "repom_redis", "redis-cli", "ping")


def test_redis_rotation_masks_passwords_and_keeps_input_for_execution():
    plan = RedisCredentialRotationPlan(
        old_password="old-secret",
        new_password="new-secret",
        container_name="repom_redis",
    )

    result = rotate_redis_password(plan, dry_run=True)

    assert result.dry_run is True
    assert "old-secret" not in " ".join(result.command)
    assert "new-secret" in result.input_text
    assert "old-secret" not in result.masked_command
    assert "new-secret" not in result.masked_input
    assert "***" in result.masked_input


def test_redis_rotation_executes_with_stdin():
    runner = MagicMock()
    runner.return_value = MagicMock(returncode=0, stdout="OK\n", stderr="")
    plan = RedisCredentialRotationPlan(
        old_password="old-secret",
        new_password="new-secret",
        container_name="repom_redis",
    )

    rotate_redis_password(plan, dry_run=False, runner=runner)

    command = runner.call_args.args[0]
    kwargs = runner.call_args.kwargs
    assert command[0:3] == ("docker", "exec", "-i")
    assert kwargs["input"] == "CONFIG SET requirepass new-secret\n"
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True
    assert "old-secret" not in " ".join(command)


def test_redis_plan_from_config_does_not_infer_old_password():
    mock_config = MagicMock()
    mock_config.redis.password = "configured-final-secret"
    mock_config.redis.container.get_container_name.return_value = "repom_redis"

    with patch("repom.redis.credentials.config", mock_config):
        plan = RedisCredentialRotationPlan.from_config(
            new_password="configured-final-secret",
        )

    assert plan.old_password is None
    assert plan.new_password == "configured-final-secret"


def test_redis_rotation_from_unauthenticated_omits_rediscli_auth():
    plan = RedisCredentialRotationPlan(
        new_password="new-secret",
        container_name="repom_redis",
    )

    result = rotate_redis_password(plan, dry_run=True)

    assert "REDISCLI_AUTH" not in " ".join(result.command)


def test_redis_rotation_uses_auth_only_when_old_password_is_explicit():
    plan = RedisCredentialRotationPlan(
        old_password="old-secret",
        new_password="new-secret",
        container_name="repom_redis",
    )

    result = rotate_redis_password(plan, dry_run=True)

    assert "--env-file" in result.command
    assert "old-secret" not in " ".join(result.command)


def test_redis_rotation_password_not_in_argv():
    """Neither the old nor the new password ever appears in any recorded argv."""
    calls: list[tuple] = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return MagicMock(returncode=0, stdout="OK\n", stderr="")

    plan = RedisCredentialRotationPlan(
        old_password="sentinel-old-secret",
        new_password="sentinel-new-secret",
        container_name="repom_redis",
    )

    result = rotate_redis_password(plan, dry_run=False, runner=fake_runner)

    assert calls, "runner was never invoked"
    for command in calls:
        joined = " ".join(command)
        assert "sentinel-old-secret" not in joined
        assert "sentinel-new-secret" not in joined
    assert "sentinel-old-secret" not in " ".join(result.command)
    assert "sentinel-new-secret" not in " ".join(result.command)


def test_redis_rotation_failure_masks_password():
    runner = MagicMock()
    runner.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="ERR invalid password: sentinel-old-secret",
    )
    plan = RedisCredentialRotationPlan(
        old_password="sentinel-old-secret",
        new_password="sentinel-new-secret",
        container_name="repom_redis",
    )

    with pytest.raises(RedisCredentialRotationError) as excinfo:
        rotate_redis_password(plan, dry_run=False, runner=runner)

    assert "sentinel-old-secret" not in str(excinfo.value)
    assert "sentinel-new-secret" not in str(excinfo.value)
    assert "***" in str(excinfo.value)


def test_redis_rotate_password_requires_explicit_new_password():
    with pytest.raises(ValueError, match="new_password"):
        rotate_password()


def test_redis_rotate_password_rejects_empty_new_password():
    with pytest.raises(ValueError, match="new_password must not be empty"):
        rotate_password("")


def test_redis_main_reads_new_password_from_stdin_without_command_exposure(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["redis_rotate_password", "--new-password-stdin"],
    )
    monkeypatch.setattr(sys, "stdin", StringIO("new-secret\n"))

    with patch("repom.redis.manage.rotate_password") as rotate:
        main_rotate_password()

    assert rotate.call_args.kwargs["new_password"] == "new-secret"
    assert "new-secret" not in " ".join(sys.argv)


def test_redis_main_prompts_for_new_password_in_a_tty(monkeypatch):
    stdin = MagicMock()
    stdin.isatty.return_value = True
    monkeypatch.setattr(sys, "argv", ["redis_rotate_password"])
    monkeypatch.setattr(sys, "stdin", stdin)

    with patch("repom.credentials.getpass.getpass", side_effect=["new-secret", ""]):
        with patch("repom.redis.manage.rotate_password") as rotate:
            main_rotate_password()

    assert rotate.call_args.kwargs["new_password"] == "new-secret"
