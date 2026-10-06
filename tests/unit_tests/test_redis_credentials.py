"""Tests for Redis credential helpers."""

from io import StringIO
import sys
from unittest.mock import MagicMock, patch

import pytest

from repom.config import config
from repom.redis.credentials import (
    RedisCredentialRotationError,
    RedisCredentialRotationPlan,
    RedisCredentialRotationResult,
    build_redis_cli_command,
    build_redis_ping_command,
    rotate_redis_password,
)
from repom.redis import manage as redis_manage
from repom.redis.manage import (
    main_rotate_password,
    rotate_password,
    rotate_redis_password_cli,
)


def test_redis_cli_command_without_env_file():
    command = build_redis_cli_command(container_name="repom_redis")

    assert command == ("docker", "exec", "-i", "repom_redis", "redis-cli")


def test_redis_cli_command_uses_env_file_when_given(tmp_path):
    env_file = tmp_path / "repom-redis-auth-xyz.env"
    command = build_redis_cli_command(
        container_name="repom_redis",
        env_file=str(env_file),
    )

    assert command == (
        "docker",
        "exec",
        "-i",
        "--env-file",
        str(env_file),
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
    assert result.recreate_required is False
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

    result = rotate_redis_password(plan, dry_run=False, runner=runner)
    assert result.recreate_required is True

    command = runner.call_args.args[0]
    kwargs = runner.call_args.kwargs
    assert command[0:3] == ("docker", "exec", "-i")
    assert kwargs["input"] == 'CONFIG SET requirepass "new-secret"\n'
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True
    assert "old-secret" not in " ".join(command)


def test_redis_rotation_quotes_password_with_spaces_and_quotes():
    runner = MagicMock()
    runner.return_value = MagicMock(returncode=0, stdout="OK\n", stderr="")
    plan = RedisCredentialRotationPlan(
        old_password="old-secret",
        new_password='new password "quoted"',
        container_name="repom_redis",
    )

    rotate_redis_password(plan, dry_run=False, runner=runner)

    assert runner.call_args.kwargs["input"] == (
        r'CONFIG SET requirepass "new password \"quoted\""' + "\n"
    )


def test_redis_rotation_rejects_error_reply_even_when_command_exits_zero():
    runner = MagicMock()
    runner.return_value = MagicMock(
        returncode=0,
        stdout="(error) ERR rejected sentinel-new-secret",
        stderr="",
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


def test_redis_rotate_does_not_regenerate_env_after_error_reply(tmp_path):
    env_file = tmp_path / ".env"
    original_env = 'REDIS_PASSWORD="old-secret"\n'
    env_file.write_text(original_env, encoding="utf-8")
    runner = MagicMock()
    runner.return_value = MagicMock(
        returncode=0,
        stdout="(error) NOAUTH Authentication required.\n",
        stderr="",
    )

    def rotate_with_fake_runner(plan, *, dry_run):
        return rotate_redis_password(plan, dry_run=dry_run, runner=runner)

    with patch.object(config.redis, "password", "old-secret"):
        with patch.object(
            redis_manage, "rotate_redis_password", side_effect=rotate_with_fake_runner
        ):
            with patch.object(
                redis_manage,
                "generate",
                side_effect=lambda: env_file.write_text(
                    'REDIS_PASSWORD="new-secret"\n', encoding="utf-8"
                ),
            ) as generate:
                with pytest.raises(RedisCredentialRotationError):
                    rotate_password(
                        "new-secret", old_password="old-secret", dry_run=False
                    )

    generate.assert_not_called()
    assert env_file.read_text(encoding="utf-8") == original_env


def test_redis_rotate_rewrites_generated_env_after_success(capsys):
    result = RedisCredentialRotationResult(
        dry_run=False,
        command=("docker", "exec", "repom_redis", "redis-cli"),
        input_text="CONFIG SET requirepass new-secret\n",
        masked_command="docker exec repom_redis redis-cli",
        masked_input="CONFIG SET requirepass ***",
        recreate_required=True,
    )

    with patch.object(config.redis, "password", "old-secret"):
        with patch.object(redis_manage, "rotate_redis_password", return_value=result):
            with patch.object(redis_manage, "generate") as generate:
                rotate_password("new-secret", old_password="old-secret", dry_run=False)

                assert config.redis.password == "new-secret"
                generate.assert_called_once_with(overwrite_secrets=True)

    output = capsys.readouterr().out
    assert "ACTION REQUIRED" in output
    assert "redis_stop" in output
    assert "redis_start" in output
    assert "new-secret" not in output


def test_redis_rotation_dry_run_prints_recreate_planning_note(capsys):
    result = rotate_password(
        "new-secret", old_password="old-secret", dry_run=True
    )

    assert result.recreate_required is False
    output = capsys.readouterr().out
    assert "executed Redis password rotation requires a container recreate" in output
    assert "redis_stop" in output
    assert "redis_start" in output
    assert "new-secret" not in output


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


@pytest.mark.parametrize(
    "new_password",
    [
        "dummy'quoted",
        r"dummy\backslash",
        'dummy"quoted',
        "dummy password",
        "dummy $repom_rotation$ tagged",
    ],
)
def test_redis_rotation_redacts_display_input_before_escaping(
    new_password, monkeypatch, capsys
):
    old_password = 'old "quoted"\\slash'
    executed_inputs = []

    def fake_runner(command, **kwargs):
        executed_inputs.append(kwargs["input"])
        return MagicMock(returncode=0, stdout="OK\n", stderr="")

    def rotate_with_fake_runner(plan, *, dry_run):
        return rotate_redis_password(plan, dry_run=dry_run, runner=fake_runner)

    monkeypatch.setattr(redis_manage, "rotate_redis_password", rotate_with_fake_runner)
    monkeypatch.setattr(redis_manage, "generate", lambda **kwargs: None)

    with patch.object(config.redis, "password", old_password):
        dry_result = rotate_redis_password_cli(
            new_password=new_password,
            old_password=old_password,
            execute=False,
        )
        dry_output = capsys.readouterr().out
        executed_result = rotate_redis_password_cli(
            new_password=new_password,
            old_password=old_password,
            execute=True,
        )
        executed_output = capsys.readouterr().out

    escaped_password = new_password.replace("\\", "\\\\").replace('"', '\\"')
    escaped_old_password = old_password.replace("\\", "\\\\").replace('"', '\\"')
    for display in (
        dry_output,
        executed_output,
        dry_result.masked_command,
        dry_result.masked_input,
        executed_result.masked_command,
        executed_result.masked_input,
    ):
        for secret in (
            new_password,
            escaped_password,
            old_password,
            escaped_old_password,
        ):
            assert secret not in display

    expected_input = f'CONFIG SET requirepass "{escaped_password}"\n'
    assert executed_result.input_text == expected_input
    assert executed_inputs == [expected_input]
    assert "--env-file" in executed_result.command


@pytest.mark.parametrize("returncode", [0, 1])
def test_redis_rotation_masks_escaped_passwords_from_failure_output(returncode):
    old_password = 'old "quoted"\\slash'
    new_password = 'new "quoted"\\slash'
    escaped_old_password = old_password.replace("\\", "\\\\").replace('"', '\\"')
    escaped_password = new_password.replace("\\", "\\\\").replace('"', '\\"')

    def fake_runner(command, **kwargs):
        if returncode:
            return MagicMock(
                returncode=returncode,
                stdout="",
                stderr=f"ERR context={kwargs['input']} old={escaped_old_password}",
            )
        return MagicMock(
            returncode=returncode,
            stdout=f"(error) rejected {escaped_password}",
            stderr="",
        )

    plan = RedisCredentialRotationPlan(
        old_password=old_password,
        new_password=new_password,
        container_name="repom_redis",
    )

    with pytest.raises(RedisCredentialRotationError) as excinfo:
        rotate_redis_password(plan, dry_run=False, runner=fake_runner)

    messages = []
    pending = [excinfo.value]
    seen = set()
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        messages.append(str(error))
        pending.extend(
            cause for cause in (error.__cause__, error.__context__) if cause
        )
    combined_message = "\n".join(messages)
    for secret in (
        old_password,
        escaped_old_password,
        new_password,
        escaped_password,
    ):
        assert secret not in combined_message
    assert "***" in combined_message


def test_redis_rotation_masks_escaped_trailing_backslash_from_failure_output():
    new_password = "ending\\"
    escaped_password = new_password.replace("\\", "\\\\").replace('"', '\\"')

    def fake_runner(command, **kwargs):
        return MagicMock(
            returncode=1,
            stdout="",
            stderr=f"ERR password={escaped_password}",
        )

    plan = RedisCredentialRotationPlan(
        new_password=new_password,
        container_name="repom_redis",
    )

    with pytest.raises(RedisCredentialRotationError) as excinfo:
        rotate_redis_password(plan, dry_run=False, runner=fake_runner)

    assert str(excinfo.value).endswith("stderr=ERR password=***")


def test_redis_rotate_password_requires_explicit_new_password():
    with pytest.raises(ValueError, match="new_password"):
        rotate_password()


def test_redis_rotate_password_rejects_empty_new_password():
    with pytest.raises(ValueError, match="new_password must not be empty"):
        rotate_password("")


def test_redis_rotation_validates_generated_values_before_live_change():
    with patch.object(config.redis, "password", "old-secret"):
        with patch.object(
            redis_manage,
            "_validate_generation",
            side_effect=ValueError("invalid generated value"),
        ):
            with patch.object(redis_manage, "rotate_redis_password") as rotate:
                with pytest.raises(ValueError, match="invalid generated value"):
                    rotate_password(
                        "new-secret", old_password="old-secret", dry_run=False
                    )

    rotate.assert_not_called()


def test_redis_rotation_reports_recovery_if_file_persistence_fails(capsys):
    result = RedisCredentialRotationResult(
        dry_run=False,
        command=("docker", "exec", "repom_redis", "redis-cli"),
        input_text="CONFIG SET requirepass new-secret\n",
        masked_command="docker exec repom_redis redis-cli",
        masked_input="CONFIG SET requirepass ***",
    )

    with patch.object(config.redis, "password", "old-secret"):
        with patch.object(redis_manage, "_validate_generation"):
            with patch.object(redis_manage, "rotate_redis_password", return_value=result):
                with patch.object(
                    redis_manage, "generate", side_effect=OSError("disk unavailable")
                ):
                    with pytest.raises(
                        RedisCredentialRotationError, match="force-regenerate"
                    ):
                        rotate_password(
                            "new-secret", old_password="old-secret", dry_run=False
                        )

    assert "Recovery required" in capsys.readouterr().out


def test_redis_main_reads_new_password_from_stdin_without_command_exposure(monkeypatch):
    monkeypatch.setattr(sys, "stdin", StringIO("new-secret\n"))

    with patch("repom.redis.manage.rotate_password") as rotate:
        main_rotate_password(["--new-password-stdin"])

    assert rotate.call_args.kwargs["new_password"] == "new-secret"
    assert "new-secret" not in " ".join(sys.argv)


def test_redis_password_cli_is_callable_without_argv(monkeypatch):
    with patch("repom.redis.manage.rotate_password") as rotate:
        rotate_redis_password_cli(new_password="new-secret")

    assert rotate.call_args.kwargs["new_password"] == "new-secret"
    assert rotate.call_args.kwargs["dry_run"] is True


def test_redis_main_prompts_for_new_password_in_a_tty(monkeypatch):
    stdin = MagicMock()
    stdin.isatty.return_value = True
    monkeypatch.setattr(sys, "argv", ["redis_rotate_password"])
    monkeypatch.setattr(sys, "stdin", stdin)

    with patch("repom.credentials.getpass.getpass", side_effect=["new-secret", ""]):
        with patch("repom.redis.manage.rotate_password") as rotate:
            main_rotate_password()

    assert rotate.call_args.kwargs["new_password"] == "new-secret"


def test_redis_main_requires_old_password_for_non_tty_execution(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["redis_rotate_password", "--new-password-stdin", "--execute"],
    )
    monkeypatch.setattr(sys, "stdin", StringIO("new-secret\n"))

    with pytest.raises(ValueError, match="--old-password-stdin"):
        main_rotate_password()
