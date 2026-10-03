"""Tests for PostgreSQL and pgAdmin credential helpers."""

from io import StringIO
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from repom.postgres.credentials import (
    PgAdminCredentialRotationError,
    PgAdminCredentialRotationPlan,
    PostgresCredentialRotationError,
    PostgresCredentialRotationPlan,
    build_pgadmin_update_password_command,
    build_postgres_rotation_steps,
    build_pgadmin_volume_recreation_commands,
    quote_identifier,
    quote_literal,
    recreate_pgadmin_volume,
    rotate_pgadmin_password,
    rotate_pgadmin_credentials_cli,
    rotate_postgres_credentials,
    rotate_postgres_credentials_cli,
    main_pgadmin,
    main_postgres,
)


def _configure_temp_secret_generation(monkeypatch, tmp_path):
    from repom.postgres import manage

    compose_dir = tmp_path / "postgres"
    init_dir = compose_dir / "postgresql_init"
    init_dir.mkdir(parents=True)
    env_file = compose_dir / ".env"
    original_env = (
        'POSTGRES_PASSWORD="postgres-old-secret"\n'
        'PGADMIN_DEFAULT_PASSWORD="pgadmin-old-secret"\n'
    )
    env_file.write_text(original_env, encoding="utf-8")

    postgres_container = SimpleNamespace(
        get_container_name=lambda: "repom_postgres",
        get_volume_name=lambda: "repom_postgres_data",
        host_port=5432,
    )
    pgadmin_container = SimpleNamespace(
        enabled=True,
        get_container_name=lambda: "repom_pgadmin",
        get_volume_name=lambda: "repom_pgadmin_data",
        host_port=5050,
    )
    mock_config = SimpleNamespace(
        data_path=tmp_path / "data",
        db_name="repom",
        postgres=SimpleNamespace(
            user="repom",
            password="postgres-config-secret",
            container=postgres_container,
        ),
        pgadmin=SimpleNamespace(
            email="admin@example.com",
            password="pgadmin-config-secret",
            container=pgadmin_container,
        ),
    )

    monkeypatch.setattr("repom.postgres.credentials.config", mock_config)
    monkeypatch.setattr(manage, "config", mock_config)
    monkeypatch.setattr(
        manage.PostgresManager, "get_compose_dir", lambda self: compose_dir
    )
    monkeypatch.setattr(manage.PostgresManager, "get_init_dir", lambda self: init_dir)
    monkeypatch.setattr(manage, "generate_docker_compose", lambda **kwargs: MagicMock())
    monkeypatch.setattr(manage, "generate_init_sql", lambda **kwargs: "-- test init\n")
    monkeypatch.setattr(manage, "generate_pgadmin_servers_json", lambda: {})
    return mock_config, env_file, original_env


def _rotation_runner(returncode=0):
    def run(command, **kwargs):
        if kwargs.get("check") and returncode:
            raise subprocess.CalledProcessError(returncode, command)
        return subprocess.CompletedProcess(
            command,
            returncode,
            stdout="",
            stderr="rotation failed" if returncode else "",
        )

    return run


def _run_rotation(operation, *, execute, runner):
    if operation == "postgres":
        plan = PostgresCredentialRotationPlan(
            current_user="repom",
            current_password="postgres-old-secret",
            new_password="postgres-rotated-secret",
            databases=(),
            container_name="repom_postgres",
        )
        return rotate_postgres_credentials(plan, dry_run=not execute, runner=runner)
    if operation == "pgadmin":
        plan = PgAdminCredentialRotationPlan(
            email="admin@example.com",
            new_password="pgadmin-rotated-secret",
            container_name="repom_pgadmin",
        )
        return rotate_pgadmin_password(plan, dry_run=not execute, runner=runner)
    if operation == "volume":
        plan = PgAdminCredentialRotationPlan(
            email="admin@example.com",
            new_password="plan-password-is-unused",
            container_name="repom_pgadmin",
            volume_name="repom_pgadmin_data",
        )
        return recreate_pgadmin_volume(plan, confirm=execute, runner=runner)
    raise AssertionError(f"Unexpected rotation operation: {operation}")


def test_quote_identifier_escapes_double_quotes():
    assert quote_identifier('app"user') == '"app""user"'


def test_quote_literal_escapes_single_quotes():
    assert quote_literal("pa'ss") == "'pa''ss'"


def test_password_only_postgres_plan_masks_password():
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="old-secret",
        new_password="new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    result = rotate_postgres_credentials(plan, dry_run=True)

    assert len(result.commands) == 1
    assert "-c" not in result.commands[0]
    assert "new-secret" not in " ".join(result.commands[0])
    assert "new-secret" not in result.masked_output[0]
    assert "***" in result.masked_output[0]


def test_password_only_postgres_dry_run_changes_password_after_grants():
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="old-secret",
        new_password="new-secret",
        databases=("app",),
        schemas=("public",),
        container_name="repom_postgres",
    )

    result = rotate_postgres_credentials(plan, dry_run=True)

    assert 'ALTER ROLE "repom" WITH PASSWORD' in result.masked_output[-1]
    assert all("GRANT " in output for output in result.masked_output[:-1])


def test_replacement_user_plan_is_non_destructive_and_grants_access():
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        new_user="app_user",
        new_password="new-secret",
        databases=("app",),
        schemas=("public",),
        container_name="repom_postgres",
    )

    steps = build_postgres_rotation_steps(plan)
    sql = "\n".join(step.sql for step in steps)

    assert "CREATE ROLE" in steps[0].sql
    assert all("GRANT " in step.sql for step in steps[1:])
    assert "CREATE ROLE" in sql
    assert 'GRANT ALL PRIVILEGES ON DATABASE "app" TO "app_user";' in sql
    assert 'GRANT USAGE, CREATE ON SCHEMA "public" TO "app_user";' in sql
    assert "ALTER DEFAULT PRIVILEGES" in sql
    assert "DROP ROLE" not in sql


def test_replacement_user_sql_uses_a_dollar_tag_absent_from_credentials():
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        new_user="app$$user",
        new_password="password $$ and $repom_rotation$",
        databases=(),
        container_name="repom_postgres",
    )

    sql = build_postgres_rotation_steps(plan)[0].sql
    dollar_quote = sql.splitlines()[0].removeprefix("DO ")

    assert dollar_quote != "$$"
    assert dollar_quote not in plan.new_password
    assert dollar_quote not in plan.new_user
    assert sql.count(dollar_quote) == 2
    assert "password $$ and $repom_rotation$" in sql


def test_postgres_rotation_validates_generated_values_before_live_change(
    monkeypatch, tmp_path
):
    from repom.postgres import manage

    mock_config, _, _ = _configure_temp_secret_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(
        manage,
        "_validate_generation",
        MagicMock(side_effect=ValueError("invalid pgAdmin credential")),
    )
    runner = MagicMock()
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="postgres-old-secret",
        new_password="postgres-rotated-secret",
        databases=(),
        container_name="repom_postgres",
    )

    with pytest.raises(ValueError, match="invalid pgAdmin credential"):
        rotate_postgres_credentials(plan, dry_run=False, runner=runner)

    runner.assert_not_called()
    assert mock_config.postgres.password == "postgres-config-secret"


def test_postgres_rotation_reports_recovery_if_file_persistence_fails(
    monkeypatch, tmp_path, capsys
):
    from repom.postgres import credentials, manage

    mock_config, _, _ = _configure_temp_secret_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(manage, "_validate_generation", lambda **kwargs: None)
    monkeypatch.setattr(
        credentials,
        "_regenerate_compose_secrets",
        MagicMock(side_effect=OSError("disk unavailable")),
    )
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="postgres-old-secret",
        new_password="postgres-rotated-secret",
        databases=(),
        container_name="repom_postgres",
    )

    with pytest.raises(PostgresCredentialRotationError, match="force-regenerate"):
        rotate_postgres_credentials(plan, dry_run=False, runner=_rotation_runner())

    assert mock_config.postgres.password == "postgres-rotated-secret"
    assert "Recovery required" in capsys.readouterr().out


def test_postgres_rotation_executes_structured_commands_through_env_file(
    monkeypatch, tmp_path
):
    _configure_temp_secret_generation(monkeypatch, tmp_path)
    runner = MagicMock()
    runner.return_value = MagicMock(returncode=0, stdout="", stderr="")
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="old-secret",
        new_password="new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    rotate_postgres_credentials(plan, dry_run=False, runner=runner)

    command = runner.call_args.args[0]
    kwargs = runner.call_args.kwargs
    assert command[:3] == ("docker", "exec", "-i")
    assert command[3] == "--env-file"
    assert command[5] == "repom_postgres"
    assert "old-secret" not in " ".join(command)
    assert "new-secret" not in " ".join(command)
    assert kwargs["input"] == 'ALTER ROLE "repom" WITH PASSWORD \'new-secret\';'
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True
    assert "env" not in kwargs


def test_postgres_rotation_env_file_holds_pgpassword_only_during_the_call(
    monkeypatch, tmp_path
):
    _configure_temp_secret_generation(monkeypatch, tmp_path)
    captured = {}

    def fake_runner(command, **kwargs):
        env_file = command[command.index("--env-file") + 1]
        captured["env_file"] = env_file
        captured["exists_during_call"] = os.path.exists(env_file)
        with open(env_file, "r", encoding="utf-8") as handle:
            captured["contents"] = handle.read()
        return MagicMock(returncode=0, stdout="", stderr="")

    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="old-secret",
        new_password="new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    rotate_postgres_credentials(plan, dry_run=False, runner=fake_runner)

    assert captured["exists_during_call"] is True
    assert captured["contents"] == "PGPASSWORD=old-secret\n"
    assert not os.path.exists(captured["env_file"])


def test_postgres_grant_failure_leaves_credentials_and_env_untouched(
    monkeypatch, tmp_path
):
    mock_config, env_file, original_env = _configure_temp_secret_generation(
        monkeypatch, tmp_path
    )
    executed_sql = []

    def fail_on_grant(command, **kwargs):
        sql = kwargs["input"]
        executed_sql.append(sql)
        return subprocess.CompletedProcess(
            command,
            1 if sql.startswith("GRANT ") else 0,
            stdout="",
            stderr="grant failed",
        )

    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="postgres-old-secret",
        new_password="postgres-new-secret",
        databases=("app",),
        schemas=("public",),
        container_name="repom_postgres",
    )

    with pytest.raises(PostgresCredentialRotationError):
        rotate_postgres_credentials(plan, dry_run=False, runner=fail_on_grant)

    assert executed_sql
    assert all('ALTER ROLE "repom" WITH PASSWORD' not in sql for sql in executed_sql)
    assert mock_config.postgres.user == "repom"
    assert mock_config.postgres.password == "postgres-config-secret"
    assert env_file.read_text(encoding="utf-8") == original_env
    assert not env_file.with_name(".env.bak").exists()


def test_replacement_user_success_updates_config_and_compose_secrets(
    monkeypatch, tmp_path
):
    mock_config, env_file, original_env = _configure_temp_secret_generation(
        monkeypatch, tmp_path
    )
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        new_user="app_user",
        current_password="postgres-old-secret",
        new_password="postgres-new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    rotate_postgres_credentials(plan, dry_run=False, runner=_rotation_runner())

    assert mock_config.postgres.user == "app_user"
    assert mock_config.postgres.password == "postgres-new-secret"
    assert env_file.read_text(encoding="utf-8") == (
        'POSTGRES_PASSWORD="postgres-new-secret"\n'
        'PGADMIN_DEFAULT_PASSWORD="pgadmin-config-secret"\n'
    )
    assert env_file.with_name(".env.bak").read_text(encoding="utf-8") == original_env


def test_postgres_rotation_still_uses_stdin_and_env_file(monkeypatch, tmp_path):
    """Regression guard: PostgreSQL passwords never appear in argv.

    The current password travels through a short-lived ``docker exec
    --env-file`` (mirroring the Redis path's REDISCLI_AUTH handling) instead
    of the host process environment, and the new password travels through
    stdin as part of the SQL step.
    """
    _configure_temp_secret_generation(monkeypatch, tmp_path)
    runner = MagicMock()
    runner.return_value = MagicMock(returncode=0, stdout="", stderr="")
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="sentinel-old-secret",
        new_password="sentinel-new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    rotate_postgres_credentials(plan, dry_run=False, runner=runner)

    command = runner.call_args.args[0]
    kwargs = runner.call_args.kwargs
    assert "sentinel-old-secret" not in " ".join(command)
    assert "sentinel-new-secret" not in " ".join(command)
    assert "--env-file" in command
    assert "sentinel-new-secret" in kwargs["input"]


def test_postgres_rotation_failure_masks_password(monkeypatch, tmp_path):
    _configure_temp_secret_generation(monkeypatch, tmp_path)
    runner = MagicMock()
    runner.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="ERROR: syntax error near sentinel-new-secret",
    )
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="sentinel-old-secret",
        new_password="sentinel-new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    with pytest.raises(PostgresCredentialRotationError) as excinfo:
        rotate_postgres_credentials(plan, dry_run=False, runner=runner)

    assert "sentinel-old-secret" not in str(excinfo.value)
    assert "sentinel-new-secret" not in str(excinfo.value)
    assert "***" in str(excinfo.value)


def test_postgres_dry_run_shows_env_file_placeholder_when_current_password_set():
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        current_password="old-secret",
        new_password="new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    result = rotate_postgres_credentials(plan, dry_run=True)

    assert "--env-file" in result.commands[0]
    assert "<postgres-auth-env-file>" in result.commands[0]


def test_postgres_dry_run_omits_env_file_without_current_password():
    plan = PostgresCredentialRotationPlan(
        current_user="repom",
        new_password="new-secret",
        databases=(),
        container_name="repom_postgres",
    )

    result = rotate_postgres_credentials(plan, dry_run=True)

    assert "--env-file" not in result.commands[0]


def test_pgadmin_update_password_command_uses_setup_py():
    plan = PgAdminCredentialRotationPlan(
        email="admin@example.com",
        new_password="new-secret",
        container_name="repom_pgadmin",
    )

    command = build_pgadmin_update_password_command(plan)

    assert command == (
        "docker",
        "exec",
        "repom_pgadmin",
        "/venv/bin/python",
        "/pgadmin4/setup.py",
        "update-user",
        "admin@example.com",
        "--password",
        "new-secret",
    )


def test_pgadmin_rotation_masks_password_in_output():
    plan = PgAdminCredentialRotationPlan(
        email="admin@example.com",
        new_password="new-secret",
        container_name="repom_pgadmin",
    )

    result = rotate_pgadmin_password(plan, dry_run=True)

    assert "new-secret" not in " ".join(result.commands[0])
    assert "***" in " ".join(result.commands[0])
    assert "new-secret" not in result.masked_output[0]
    assert "***" in result.masked_output[0]


def test_pgadmin_rotation_failure_masks_password():
    runner = MagicMock()
    runner.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="setup.py: error updating user with password sentinel-new-secret",
    )
    plan = PgAdminCredentialRotationPlan(
        email="admin@example.com",
        new_password="sentinel-new-secret",
        container_name="repom_pgadmin",
    )

    with pytest.raises(PgAdminCredentialRotationError) as excinfo:
        rotate_pgadmin_password(plan, dry_run=False, runner=runner)

    assert "sentinel-new-secret" not in str(excinfo.value)
    assert "***" in str(excinfo.value)


def test_pgadmin_volume_recreation_is_dry_run_without_confirm():
    runner = MagicMock()
    plan = PgAdminCredentialRotationPlan(
        email="admin@example.com",
        new_password="new-secret",
        container_name="repom_pgadmin",
        volume_name="repom_pgadmin_data",
    )

    result = recreate_pgadmin_volume(plan, confirm=False, runner=runner)

    assert result.dry_run is True
    runner.assert_not_called()
    assert build_pgadmin_volume_recreation_commands(plan) == result.commands


def test_pgadmin_volume_recreation_executes_only_when_confirmed(monkeypatch, tmp_path):
    _configure_temp_secret_generation(monkeypatch, tmp_path)
    runner = MagicMock()
    plan = PgAdminCredentialRotationPlan(
        email="admin@example.com",
        new_password="new-secret",
        container_name="repom_pgadmin",
        volume_name="repom_pgadmin_data",
    )

    result = recreate_pgadmin_volume(plan, confirm=True, runner=runner)

    assert result.dry_run is False
    assert runner.call_count == 2


@pytest.mark.parametrize("operation", ("postgres", "pgadmin", "volume"))
def test_successful_rotation_persists_compose_secrets_and_backup(
    operation, monkeypatch, tmp_path
):
    mock_config, env_file, original_env = _configure_temp_secret_generation(
        monkeypatch, tmp_path
    )

    result = _run_rotation(operation, execute=True, runner=_rotation_runner())

    assert result.dry_run is False
    if operation == "postgres":
        postgres_password = "postgres-rotated-secret"
        pgadmin_password = "pgadmin-config-secret"
    elif operation == "pgadmin":
        postgres_password = "postgres-config-secret"
        pgadmin_password = "pgadmin-rotated-secret"
    else:
        postgres_password = "postgres-config-secret"
        pgadmin_password = "pgadmin-config-secret"
    assert mock_config.postgres.password == postgres_password
    assert mock_config.pgadmin.password == pgadmin_password
    assert env_file.read_text(encoding="utf-8") == (
        f'POSTGRES_PASSWORD="{postgres_password}"\n'
        f'PGADMIN_DEFAULT_PASSWORD="{pgadmin_password}"\n'
    )
    assert env_file.with_name(".env.bak").read_text(encoding="utf-8") == original_env


@pytest.mark.parametrize("operation", ("postgres", "pgadmin", "volume"))
def test_dry_run_leaves_compose_secrets_untouched(operation, monkeypatch, tmp_path):
    mock_config, env_file, original_env = _configure_temp_secret_generation(
        monkeypatch, tmp_path
    )
    runner = MagicMock(return_value=subprocess.CompletedProcess((), 0))

    result = _run_rotation(operation, execute=False, runner=runner)

    assert result.dry_run is True
    assert mock_config.postgres.password == "postgres-config-secret"
    assert mock_config.pgadmin.password == "pgadmin-config-secret"
    assert env_file.read_text(encoding="utf-8") == original_env
    assert not env_file.with_name(".env.bak").exists()
    runner.assert_not_called()


@pytest.mark.parametrize(
    "operation, error_type",
    (
        ("postgres", PostgresCredentialRotationError),
        ("pgadmin", PgAdminCredentialRotationError),
        ("volume", subprocess.CalledProcessError),
    ),
)
def test_failed_rotation_leaves_compose_secrets_untouched(
    operation, error_type, monkeypatch, tmp_path
):
    mock_config, env_file, original_env = _configure_temp_secret_generation(
        monkeypatch, tmp_path
    )

    with pytest.raises(error_type):
        _run_rotation(
            operation,
            execute=True,
            runner=_rotation_runner(returncode=1),
        )

    assert mock_config.postgres.password == "postgres-config-secret"
    assert mock_config.pgadmin.password == "pgadmin-config-secret"
    assert env_file.read_text(encoding="utf-8") == original_env
    assert not env_file.with_name(".env.bak").exists()


def test_postgres_plan_from_config_uses_default_databases():
    mock_config = MagicMock()
    mock_config.db_name = "mine_py"
    mock_config.postgres.user = "repom"
    mock_config.postgres.password = "old-secret"
    mock_config.postgres.container.get_container_name.return_value = "repom_postgres"

    with patch("repom.postgres.credentials.config", mock_config):
        plan = PostgresCredentialRotationPlan.from_config(
            new_password="new-secret",
        )

    assert plan.databases == ("mine_py", "mine_py_dev", "mine_py_test")
    assert plan.container_name == "repom_postgres"


def test_postgres_main_requires_explicit_new_password_without_sql(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["postgres_rotate_credentials"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    with patch("repom.postgres.credentials.rotate_postgres_credentials") as rotate:
        with pytest.raises(ValueError, match="--new-password"):
            main_postgres()

    rotate.assert_not_called()


def test_postgres_main_rejects_empty_new_password_without_sql(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["postgres_rotate_credentials", "--new-password", ""],
    )

    with patch("repom.postgres.credentials.rotate_postgres_credentials") as rotate:
        with pytest.raises(ValueError, match="--new-password must not be empty"):
            main_postgres()

    rotate.assert_not_called()


def test_postgres_main_reads_new_password_from_stdin_without_command_exposure(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["postgres_rotate_credentials", "--new-password-stdin"],
    )
    monkeypatch.setattr(sys, "stdin", StringIO("new-secret\n"))

    with patch("repom.postgres.credentials.rotate_postgres_credentials") as rotate:
        main_postgres()

    plan = rotate.call_args.args[0]
    assert plan.new_password == "new-secret"
    assert "new-secret" not in " ".join(sys.argv)


def test_postgres_main_prompts_for_new_password_in_a_tty(monkeypatch):
    stdin = MagicMock()
    stdin.isatty.return_value = True
    monkeypatch.setattr(sys, "argv", ["postgres_rotate_credentials"])
    monkeypatch.setattr(sys, "stdin", stdin)

    with patch("repom.credentials.getpass.getpass", return_value="new-secret") as prompt:
        with patch("repom.postgres.credentials.rotate_postgres_credentials") as rotate:
            main_postgres()

    prompt.assert_called_once_with("New PostgreSQL password: ")
    assert rotate.call_args.args[0].new_password == "new-secret"


def test_postgres_main_delegates_execution_to_library():
    mock_config = MagicMock()
    mock_config.postgres.password = "old-secret"

    with patch("repom.postgres.credentials.config", mock_config):
        with patch(
            "repom.postgres.credentials.rotate_postgres_credentials",
            return_value=MagicMock(dry_run=False, masked_output=()),
        ) as rotate:
            with patch("repom.postgres.manage.generate") as generate:
                main_postgres(
                    [
                        "--new-password",
                        "new-secret",
                        "--current-password",
                        "old-secret",
                        "--execute",
                    ]
                )

    assert rotate.call_args.kwargs["dry_run"] is False
    assert mock_config.postgres.password == "old-secret"
    generate.assert_not_called()


def test_postgres_credentials_cli_is_callable_without_argv():
    with patch("repom.postgres.credentials.config", MagicMock()):
        with patch(
            "repom.postgres.credentials.rotate_postgres_credentials",
            return_value=MagicMock(dry_run=False, masked_output=()),
        ) as rotate:
            rotate_postgres_credentials_cli(
                new_password="new-secret",
                current_password="old-secret",
                current_user="repom",
                execute=True,
            )

    assert rotate.call_args.kwargs["dry_run"] is False


def test_pgadmin_main_keeps_new_password_argument_behavior(monkeypatch):
    with patch("repom.postgres.credentials.rotate_pgadmin_password") as rotate:
        main_pgadmin(["--new-password", "new-secret"])

    assert rotate.call_args.args[0].new_password == "new-secret"


def test_pgadmin_credentials_cli_is_callable_without_argv():
    with patch("repom.postgres.credentials.config", MagicMock()):
        with patch(
            "repom.postgres.credentials.rotate_pgadmin_password",
            return_value=MagicMock(dry_run=False, masked_output=()),
        ) as rotate:
            rotate_pgadmin_credentials_cli(new_password="new-secret", execute=True)

    assert rotate.call_args.kwargs["dry_run"] is False


def test_pgadmin_main_delegates_execution_to_library(monkeypatch):
    mock_config = MagicMock()
    mock_config.pgadmin.password = "old-secret"
    monkeypatch.setattr(
        sys,
        "argv",
        ["pgadmin_rotate_password", "--new-password", "new-secret", "--execute"],
    )

    with patch("repom.postgres.credentials.config", mock_config):
        with patch(
            "repom.postgres.credentials.rotate_pgadmin_password",
            return_value=MagicMock(dry_run=False, masked_output=()),
        ) as rotate:
            with patch("repom.postgres.manage.generate") as generate:
                main_pgadmin()

    assert rotate.call_args.kwargs["dry_run"] is False
    assert mock_config.pgadmin.password == "old-secret"
    generate.assert_not_called()


def test_pgadmin_main_requires_explicit_new_password(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pgadmin_rotate_password"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    with patch("repom.postgres.credentials.rotate_pgadmin_password") as rotate:
        with pytest.raises(ValueError, match="--new-password"):
            main_pgadmin()

    rotate.assert_not_called()
