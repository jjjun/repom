"""Tests for Redis credential helpers."""

from unittest.mock import MagicMock, patch

from repom.redis.credentials import (
    RedisCredentialRotationPlan,
    build_redis_cli_command,
    build_redis_ping_command,
    rotate_redis_password,
)


def test_redis_cli_command_without_password():
    command = build_redis_cli_command(container_name="repom_redis")

    assert command == ("docker", "exec", "-i", "repom_redis", "redis-cli")


def test_redis_cli_command_uses_rediscli_auth_when_password_is_set():
    command = build_redis_cli_command(
        container_name="repom_redis",
        password="old-secret",
    )

    assert command == (
        "docker",
        "exec",
        "-i",
        "-e",
        "REDISCLI_AUTH=old-secret",
        "repom_redis",
        "redis-cli",
    )


def test_redis_ping_command_appends_ping():
    command = build_redis_ping_command(
        container_name="repom_redis",
        password="old-secret",
    )

    assert command[-1] == "ping"
    assert "REDISCLI_AUTH=old-secret" in command


def test_redis_rotation_masks_passwords_and_keeps_input_for_execution():
    plan = RedisCredentialRotationPlan(
        old_password="old-secret",
        new_password="new-secret",
        container_name="repom_redis",
    )

    result = rotate_redis_password(plan, dry_run=True)

    assert result.dry_run is True
    assert "old-secret" in " ".join(result.command)
    assert "new-secret" in result.input_text
    assert "old-secret" not in result.masked_command
    assert "new-secret" not in result.masked_input
    assert "***" in result.masked_command
    assert "***" in result.masked_input


def test_redis_rotation_executes_with_stdin():
    runner = MagicMock()
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
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True


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

    assert "REDISCLI_AUTH=old-secret" in result.command
