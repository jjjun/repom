"""Credential rotation helpers for Redis."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from repom.config import config


CommandRunner = Callable[..., subprocess.CompletedProcess]


class RedisCredentialRotationError(RuntimeError):
    """Raised when a Redis rotation command exits with a non-zero status."""


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
    """Result returned by Redis password rotation."""

    dry_run: bool
    command: tuple[str, ...]
    input_text: str
    masked_command: str
    masked_input: str


def mask_secret(text: str, *secrets: str | None) -> str:
    """Mask all non-empty secrets in text."""

    masked = text
    for secret in secrets:
        if secret:
            masked = masked.replace(secret, "***")
    return masked


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
    """Build an unauthenticated redis-cli PING command for readiness checks.

    Readiness polling never needs the password: a password-protected instance
    still responds with a NOAUTH error once it is up, which is enough to tell
    the caller the server is reachable.
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

    if not password:
        yield None
        return

    fd, path = tempfile.mkstemp(prefix="repom-redis-auth-", suffix=".env")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w") as handle:
            handle.write(f"REDISCLI_AUTH={password}\n")
        yield path
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def rotate_redis_password(
    plan: RedisCredentialRotationPlan,
    *,
    dry_run: bool = True,
    runner: CommandRunner = subprocess.run,
) -> RedisCredentialRotationResult:
    """Apply a new Redis requirepass value to a running instance."""

    container_name = plan.container_name or config.redis.container.get_container_name()
    input_text = f"CONFIG SET requirepass {plan.new_password}\n"
    secrets = (plan.old_password, plan.new_password)

    if not dry_run:
        with _rediscli_auth_env_file(plan.old_password) as env_file:
            command = build_redis_cli_command(container_name=container_name, env_file=env_file)
            completed = runner(
                command,
                input=input_text,
                capture_output=True,
                text=True,
                check=False,
            )

        if completed.returncode != 0:
            raise RedisCredentialRotationError(
                mask_secret(
                    f"redis-cli rotation failed (exit {completed.returncode}): "
                    f"command={' '.join(command)} stderr={completed.stderr}",
                    *secrets,
                )
            )
    else:
        placeholder_env_file = "<redis-auth-env-file>" if plan.old_password else None
        command = build_redis_cli_command(container_name=container_name, env_file=placeholder_env_file)

    masked_command = mask_secret(" ".join(command), *secrets)
    masked_input = mask_secret(input_text, *secrets)

    return RedisCredentialRotationResult(
        dry_run=dry_run,
        command=command,
        input_text=input_text,
        masked_command=masked_command,
        masked_input=masked_input,
    )
