"""Credential rotation helpers for PostgreSQL and pgAdmin."""

from __future__ import annotations

import os
import subprocess
import argparse
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from repom.config import config


CommandRunner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class SqlStep:
    """One SQL statement to run against one database."""

    database: str
    sql: str


@dataclass(frozen=True)
class PostgresCredentialRotationPlan:
    """Non-destructive PostgreSQL credential rotation plan."""

    current_user: str
    new_password: str
    current_password: str | None = None
    new_user: str | None = None
    databases: Sequence[str] = field(default_factory=tuple)
    schemas: Sequence[str] = field(default_factory=lambda: ("public",))
    container_name: str | None = None
    maintenance_database: str = "postgres"

    @classmethod
    def from_config(
        cls,
        *,
        new_password: str,
        current_user: str | None = None,
        current_password: str | None = None,
        new_user: str | None = None,
        databases: Sequence[str] | None = None,
        schemas: Sequence[str] = ("public",),
    ) -> "PostgresCredentialRotationPlan":
        base = config.db_name
        return cls(
            current_user=current_user or config.postgres.user,
            current_password=current_password or config.postgres.password,
            new_password=new_password,
            new_user=new_user,
            databases=databases or (base, f"{base}_dev", f"{base}_test"),
            schemas=schemas,
            container_name=config.postgres.container.get_container_name(),
        )


@dataclass(frozen=True)
class PgAdminCredentialRotationPlan:
    """pgAdmin administrator password rotation plan."""

    email: str
    new_password: str
    container_name: str | None = None
    volume_name: str | None = None
    python_path: str = "/venv/bin/python"
    setup_py_path: str = "/pgadmin4/setup.py"

    @classmethod
    def from_config(
        cls,
        *,
        new_password: str | None = None,
    ) -> "PgAdminCredentialRotationPlan":
        return cls(
            email=config.pgadmin.email,
            new_password=new_password or config.pgadmin.password,
            container_name=config.pgadmin.container.get_container_name(),
            volume_name=config.pgadmin.container.get_volume_name(),
        )


@dataclass(frozen=True)
class CredentialRotationResult:
    """Result returned by a dry-run or executed rotation."""

    dry_run: bool
    commands: tuple[tuple[str, ...], ...]
    masked_output: tuple[str, ...]


def quote_identifier(value: str) -> str:
    """Quote a PostgreSQL identifier."""

    if not value:
        raise ValueError("identifier must not be empty")
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    """Quote a PostgreSQL string literal."""

    return "'" + value.replace("'", "''") + "'"


def mask_secret(text: str, secrets: Iterable[str]) -> str:
    """Mask all non-empty secrets in text."""

    masked = text
    for secret in secrets:
        if secret:
            masked = masked.replace(secret, "***")
    return masked


def build_postgres_rotation_steps(
    plan: PostgresCredentialRotationPlan,
) -> tuple[SqlStep, ...]:
    """Build the SQL steps for a PostgreSQL rotation plan."""

    target_user = plan.new_user or plan.current_user
    steps: list[SqlStep] = []

    if plan.new_user and plan.new_user != plan.current_user:
        role_sql = "\n".join(
            [
                "DO $$",
                "BEGIN",
                "  IF NOT EXISTS (",
                "    SELECT FROM pg_catalog.pg_roles",
                f"    WHERE rolname = {quote_literal(plan.new_user)}",
                "  ) THEN",
                (
                    f"    CREATE ROLE {quote_identifier(plan.new_user)} "
                    f"LOGIN PASSWORD {quote_literal(plan.new_password)};"
                ),
                "  ELSE",
                (
                    f"    ALTER ROLE {quote_identifier(plan.new_user)} "
                    f"WITH LOGIN PASSWORD {quote_literal(plan.new_password)};"
                ),
                "  END IF;",
                "END",
                "$$;",
            ]
        )
        steps.append(SqlStep(database=plan.maintenance_database, sql=role_sql))
    else:
        steps.append(
            SqlStep(
                database=plan.maintenance_database,
                sql=(
                    f"ALTER ROLE {quote_identifier(plan.current_user)} "
                    f"WITH PASSWORD {quote_literal(plan.new_password)};"
                ),
            )
        )

    for database in plan.databases:
        steps.append(
            SqlStep(
                database=plan.maintenance_database,
                sql=(
                    f"GRANT ALL PRIVILEGES ON DATABASE "
                    f"{quote_identifier(database)} TO {quote_identifier(target_user)};"
                ),
            )
        )
        for schema in plan.schemas:
            schema_id = quote_identifier(schema)
            target_id = quote_identifier(target_user)
            steps.extend(
                [
                    SqlStep(
                        database=database,
                        sql=f"GRANT USAGE, CREATE ON SCHEMA {schema_id} TO {target_id};",
                    ),
                    SqlStep(
                        database=database,
                        sql=f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema_id} TO {target_id};",
                    ),
                    SqlStep(
                        database=database,
                        sql=f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema_id} TO {target_id};",
                    ),
                    SqlStep(
                        database=database,
                        sql=f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_id} GRANT ALL ON TABLES TO {target_id};",
                    ),
                    SqlStep(
                        database=database,
                        sql=f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_id} GRANT ALL ON SEQUENCES TO {target_id};",
                    ),
                ]
            )

    return tuple(steps)


def build_postgres_psql_command(
    plan: PostgresCredentialRotationPlan,
    step: SqlStep,
) -> tuple[str, ...]:
    """Build a structured docker/psql command for one SQL step.

    SQL is sent through stdin by ``rotate_postgres_credentials`` so new
    passwords do not appear in process arguments.
    """

    container_name = plan.container_name or config.postgres.container.get_container_name()
    return (
        "docker",
        "exec",
        "-i",
        container_name,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        plan.current_user,
        "-d",
        step.database,
    )


def rotate_postgres_credentials(
    plan: PostgresCredentialRotationPlan,
    *,
    dry_run: bool = True,
    runner: CommandRunner = subprocess.run,
) -> CredentialRotationResult:
    """Execute or dry-run a PostgreSQL credential rotation plan."""

    steps = build_postgres_rotation_steps(plan)
    commands = tuple(build_postgres_psql_command(plan, step) for step in steps)
    secrets = (plan.current_password or "", plan.new_password)
    masked_output = tuple(
        mask_secret(f"{step.database}: {step.sql}", secrets) for step in steps
    )

    if not dry_run:
        env = os.environ.copy()
        if plan.current_password:
            env["PGPASSWORD"] = plan.current_password
        for command, step in zip(commands, steps):
            runner(command, check=True, text=True, env=env, input=step.sql)

    return CredentialRotationResult(
        dry_run=dry_run,
        commands=commands,
        masked_output=masked_output,
    )


def build_pgadmin_update_password_command(
    plan: PgAdminCredentialRotationPlan,
) -> tuple[str, ...]:
    """Build the supported pgAdmin setup.py password update command.

    pgAdmin documents ``setup.py update-user`` with ``--password`` as a command
    argument and does not document a stdin or environment-variable password
    input. The new password is therefore visible to host process-list readers
    while this short-lived command runs.
    """

    container_name = plan.container_name or config.pgadmin.container.get_container_name()
    return (
        "docker",
        "exec",
        container_name,
        plan.python_path,
        plan.setup_py_path,
        "update-user",
        plan.email,
        "--password",
        plan.new_password,
    )


def rotate_pgadmin_password(
    plan: PgAdminCredentialRotationPlan,
    *,
    dry_run: bool = True,
    runner: CommandRunner = subprocess.run,
) -> CredentialRotationResult:
    """Rotate the pgAdmin admin password with setup.py update-user."""

    command = build_pgadmin_update_password_command(plan)
    masked_command = mask_secret(" ".join(command), (plan.new_password,))
    if not dry_run:
        runner(command, check=True, text=True)
    return CredentialRotationResult(
        dry_run=dry_run,
        commands=(command,),
        masked_output=(masked_command,),
    )


def build_pgadmin_volume_recreation_commands(
    plan: PgAdminCredentialRotationPlan,
) -> tuple[tuple[str, ...], ...]:
    """Build commands for the fallback that recreates only the pgAdmin volume."""

    container_name = plan.container_name or config.pgadmin.container.get_container_name()
    volume_name = plan.volume_name or config.pgadmin.container.get_volume_name()
    return (
        ("docker", "rm", "-f", container_name),
        ("docker", "volume", "rm", volume_name),
    )


def recreate_pgadmin_volume(
    plan: PgAdminCredentialRotationPlan,
    *,
    confirm: bool = False,
    runner: CommandRunner = subprocess.run,
) -> CredentialRotationResult:
    """Recreate only the pgAdmin volume after compose regeneration.

    This helper intentionally requires ``confirm=True`` because it deletes
    pgAdmin's own saved UI state. It does not delete PostgreSQL data volumes.
    """

    commands = build_pgadmin_volume_recreation_commands(plan)
    masked_output = tuple(" ".join(command) for command in commands)
    if not confirm:
        return CredentialRotationResult(
            dry_run=True,
            commands=commands,
            masked_output=masked_output,
        )
    for command in commands:
        runner(command, check=True, text=True)
    return CredentialRotationResult(
        dry_run=False,
        commands=commands,
        masked_output=masked_output,
    )


def _print_result(result: CredentialRotationResult) -> None:
    action = "Dry-run" if result.dry_run else "Executed"
    print(f"{action} credential rotation plan:")
    for line in result.masked_output:
        print(line)


def main_postgres() -> None:
    """Console entry point for PostgreSQL credential rotation."""

    parser = argparse.ArgumentParser(
        description="Rotate credentials for a running repom PostgreSQL container."
    )
    parser.add_argument("--new-password", default=None)
    parser.add_argument("--current-user", default=None)
    parser.add_argument("--current-password", default=None)
    parser.add_argument("--new-user", default=None)
    parser.add_argument("--database", action="append", dest="databases")
    parser.add_argument("--schema", action="append", dest="schemas")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the rotation. Without this flag, only a dry-run is printed.",
    )
    args = parser.parse_args()

    new_password = args.new_password or config.postgres.password
    if not new_password:
        raise ValueError("--new-password or config.postgres.password is required")

    plan = PostgresCredentialRotationPlan.from_config(
        current_user=args.current_user,
        current_password=args.current_password,
        new_password=new_password,
        new_user=args.new_user,
        databases=args.databases,
        schemas=tuple(args.schemas or ("public",)),
    )
    result = rotate_postgres_credentials(plan, dry_run=not args.execute)
    _print_result(result)


def main_pgadmin() -> None:
    """Console entry point for pgAdmin password rotation."""

    parser = argparse.ArgumentParser(
        description="Rotate the pgAdmin admin password for a repom container."
    )
    parser.add_argument("--new-password", default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the update-user command. Default is dry-run.",
    )
    parser.add_argument(
        "--recreate-volume",
        action="store_true",
        help="Print or run fallback commands that recreate only the pgAdmin volume.",
    )
    parser.add_argument(
        "--confirm-recreate-volume",
        action="store_true",
        help="Required with --recreate-volume to actually delete pgAdmin state.",
    )
    args = parser.parse_args()

    plan = PgAdminCredentialRotationPlan.from_config(
        new_password=args.new_password,
    )
    if args.recreate_volume:
        result = recreate_pgadmin_volume(
            plan,
            confirm=args.execute and args.confirm_recreate_volume,
        )
    else:
        result = rotate_pgadmin_password(plan, dry_run=not args.execute)
    _print_result(result)
