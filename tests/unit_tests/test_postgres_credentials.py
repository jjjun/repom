"""Tests for PostgreSQL and pgAdmin credential helpers."""

from io import StringIO
import sys
from unittest.mock import MagicMock, patch

import pytest

from repom.postgres.credentials import (
    PgAdminCredentialRotationError,
    PgAdminCredentialRotationPlan,
    PostgresCredentialRotationPlan,
    build_pgadmin_update_password_command,
    build_postgres_rotation_steps,
    build_pgadmin_volume_recreation_commands,
    quote_identifier,
    quote_literal,
    recreate_pgadmin_volume,
    rotate_pgadmin_password,
    rotate_postgres_credentials,
    main_pgadmin,
    main_postgres,
)


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

    assert "CREATE ROLE" in sql
    assert 'GRANT ALL PRIVILEGES ON DATABASE "app" TO "app_user";' in sql
    assert 'GRANT USAGE, CREATE ON SCHEMA "public" TO "app_user";' in sql
    assert "ALTER DEFAULT PRIVILEGES" in sql
    assert "DROP ROLE" not in sql


def test_postgres_rotation_executes_structured_commands_with_pgpassword():
    runner = MagicMock()
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
    assert command[:4] == ("docker", "exec", "-i", "repom_postgres")
    assert "new-secret" not in " ".join(command)
    assert kwargs["input"] == 'ALTER ROLE "repom" WITH PASSWORD \'new-secret\';'
    assert kwargs["env"]["PGPASSWORD"] == "old-secret"
    assert kwargs["check"] is True


def test_postgres_rotation_still_uses_stdin_and_env():
    """Regression guard: the PostgreSQL path stays the correct reference pattern.

    Unlike Redis and pgAdmin, PostgreSQL never had a password in argv: the
    current password travels through the ``PGPASSWORD`` environment variable
    and the new password travels through stdin as part of the SQL step.
    """
    runner = MagicMock()
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
    assert kwargs["env"]["PGPASSWORD"] == "sentinel-old-secret"
    assert "sentinel-new-secret" in kwargs["input"]


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


def test_rotation_result_commands_are_masked():
    """No field of a CredentialRotationResult carries the sentinel in cleartext."""
    plan = PgAdminCredentialRotationPlan(
        email="admin@example.com",
        new_password="sentinel-new-secret",
        container_name="repom_pgadmin",
    )

    result = rotate_pgadmin_password(plan, dry_run=True)

    for command in result.commands:
        assert "sentinel-new-secret" not in " ".join(command)
    for line in result.masked_output:
        assert "sentinel-new-secret" not in line


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


def test_pgadmin_volume_recreation_executes_only_when_confirmed():
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


def test_pgadmin_main_keeps_new_password_argument_behavior(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["pgadmin_rotate_password", "--new-password", "new-secret"],
    )

    with patch("repom.postgres.credentials.rotate_pgadmin_password") as rotate:
        main_pgadmin()

    assert rotate.call_args.args[0].new_password == "new-secret"


def test_pgadmin_main_requires_explicit_new_password(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pgadmin_rotate_password"])
    monkeypatch.setattr(sys, "stdin", StringIO(""))

    with patch("repom.postgres.credentials.rotate_pgadmin_password") as rotate:
        with pytest.raises(ValueError, match="--new-password"):
            main_pgadmin()

    rotate.assert_not_called()
