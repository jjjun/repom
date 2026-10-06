"""Credential rotation helpers for Redis."""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Iterator

from repom.config import config
from repom.docker_compose_safety import reject_control_characters
from repom.credentials import (
    CommandRunner,
    mask_secret as _mask_secret,
    run_masked_command,
    secret_env_file,
)


class RedisCredentialRotationError(RuntimeError):
    """Raised when Redis rejects a password rotation command."""


@dataclass(frozen=True)
class RedisCredentialRotationPlan:
    """Redis password rotation plan."""

    new_password: str
    old_password: str | None = None
    container_name: str | None = None

    @classmethod
    def from_config(
        cls,
        *,
        new_password: str,
        old_password: str | None = None,
    ) -> "RedisCredentialRotationPlan":
        return cls(
            old_password=old_password,
            new_password=new_password,
            container_name=config.redis.container.get_container_name(),
        )


@dataclass(frozen=True)
class RedisCredentialRotationResult:
    """Result returned by Redis password rotation.

    ``input_text`` contains the unredacted execution payload and must be
    treated as a secret.
    """

    dry_run: bool
    command: tuple[str, ...]
    input_text: str
    masked_command: str
    masked_input: str
    recreate_required: bool = False


def mask_secret(text: str, *secrets: str | None) -> str:
    """Mask all non-empty secrets in text."""

    return _mask_secret(text, secrets)


def build_redis_cli_command(
    *,
    container_name: str,
    env_file: str | None = None,
) -> tuple[str, ...]:
    """Build a docker exec redis-cli command.

    When ``env_file`` is supplied it is passed to ``docker exec --env-file``,
    so the container reads REDISCLI_AUTH from that file's contents instead of
    the value appearing as a docker exec argument. Callers that need
    authentication build the file with :func:`_rediscli_auth_env_file`.
    """

    command = ["docker", "exec", "-i"]
    if env_file:
        command.extend(["--env-file", env_file])
    command.extend([container_name, "redis-cli"])
    return tuple(command)


def build_redis_ping_command(
    *,
    container_name: str,
) -> tuple[str, ...]:
    """Build a redis-cli PING command for readiness checks.

    docker exec inherits REDISCLI_AUTH from the container environment, so the
    ping authenticates with the creation-time password. After an in-place
    rotation that password is stale, and NOAUTH is accepted as a readiness
    signal.
    """

    command = list(build_redis_cli_command(container_name=container_name))
    command.append("ping")
    return tuple(command)


@contextmanager
def _rediscli_auth_env_file(password: str | None) -> Iterator[str | None]:
    """Yield a 0600 temp file path holding REDISCLI_AUTH, or None.

    The file is removed as soon as the caller is done with it, keeping the
    window in which the password exists on disk as short as possible.
    """

    with secret_env_file("REDISCLI_AUTH", password, prefix="repom-redis-auth-") as path:
        yield path


def rotate_redis_password(
    plan: RedisCredentialRotationPlan,
    *,
    dry_run: bool = True,
    runner: CommandRunner = subprocess.run,
) -> RedisCredentialRotationResult:
    """Apply a new Redis requirepass value to a running instance."""

    container_name = plan.container_name or config.redis.container.get_container_name()
    new_password = reject_control_characters(
        plan.new_password, field_name="new_password"
    )
    escaped_password = new_password.replace("\\", "\\\\").replace('"', '\\"')
    input_text = f'CONFIG SET requirepass "{escaped_password}"\n'
    escaped_old_password = (
        plan.old_password.replace("\\", "\\\\").replace('"', '\\"')
        if plan.old_password is not None
        else None
    )
    secrets = (
        plan.old_password,
        escaped_old_password,
        plan.new_password,
        escaped_password,
    )
    display_plan = replace(plan, old_password=None, new_password="***")
    display_escaped_password = (
        display_plan.new_password.replace("\\", "\\\\").replace('"', '\\"')
    )
    display_input_text = (
        f'CONFIG SET requirepass "{display_escaped_password}"\n'
    )

    if not dry_run:
        with _rediscli_auth_env_file(plan.old_password) as env_file:
            command = build_redis_cli_command(container_name=container_name, env_file=env_file)
            completed = run_masked_command(
                command,
                runner=runner,
                secrets=secrets,
                error_type=RedisCredentialRotationError,
                action="redis-cli rotation",
                input=input_text,
            )
        if (completed.stdout or "").strip() != "OK":
            output = mask_secret(
                f"stdout={(completed.stdout or '').strip()} "
                f"stderr={(completed.stderr or '').strip()}",
                *secrets,
            )
            raise RedisCredentialRotationError(
                f"redis-cli rotation returned an unexpected reply: {output}"
            )
    else:
        placeholder_env_file = "<redis-auth-env-file>" if plan.old_password else None
        command = build_redis_cli_command(container_name=container_name, env_file=placeholder_env_file)

    masked_command = mask_secret(" ".join(command), *secrets)
    masked_input = mask_secret(display_input_text, *secrets)

    return RedisCredentialRotationResult(
        dry_run=dry_run,
        command=command,
        input_text=input_text,
        masked_command=masked_command,
        masked_input=masked_input,
        recreate_required=not dry_run,
    )
