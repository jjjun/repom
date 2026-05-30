"""Credential rotation helpers for Redis."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable

from repom.config import config


CommandRunner = Callable[..., subprocess.CompletedProcess]


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
            old_password=old_password or config.redis.password,
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
    password: str | None = None,
) -> tuple[str, ...]:
    """Build a docker exec redis-cli command.

    When a password is supplied it is passed through REDISCLI_AUTH so it does
    not appear in the command arguments.
    """

    command = ["docker", "exec", "-i"]
    if password:
        command.extend(["-e", f"REDISCLI_AUTH={password}"])
    command.extend([container_name, "redis-cli"])
    return tuple(command)


def build_redis_ping_command(
    *,
    container_name: str,
    password: str | None = None,
) -> tuple[str, ...]:
    """Build a redis-cli PING command for readiness checks."""

    command = list(build_redis_cli_command(container_name=container_name, password=password))
    command.append("ping")
    return tuple(command)


def rotate_redis_password(
    plan: RedisCredentialRotationPlan,
    *,
    dry_run: bool = True,
    runner: CommandRunner = subprocess.run,
) -> RedisCredentialRotationResult:
    """Apply a new Redis requirepass value to a running instance."""

    container_name = plan.container_name or config.redis.container.get_container_name()
    command = build_redis_cli_command(
        container_name=container_name,
        password=plan.old_password,
    )
    input_text = f"CONFIG SET requirepass {plan.new_password}\n"
    masked_command = mask_secret(" ".join(command), plan.old_password, plan.new_password)
    masked_input = mask_secret(input_text, plan.old_password, plan.new_password)

    if not dry_run:
        runner(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            check=True,
        )

    return RedisCredentialRotationResult(
        dry_run=dry_run,
        command=command,
        input_text=input_text,
        masked_command=masked_command,
        masked_input=masked_input,
    )
