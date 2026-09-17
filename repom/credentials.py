"""Shared password input helpers for credential rotation commands."""

from __future__ import annotations

import getpass
import os
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from typing import Callable, Iterable, Iterator, Sequence, TextIO


def resolve_password(
    *,
    password: str | None,
    read_stdin: bool,
    allow_config_password: bool = False,
    config_password: str | None = None,
    prompt: str,
    option_name: str,
    stdin: TextIO | None = None,
    allow_empty: bool = False,
) -> str | None:
    """Resolve a password without requiring it in a process argument."""

    stdin = stdin or sys.stdin
    if password is not None:
        resolved_password = password
    elif read_stdin:
        resolved_password = stdin.readline().rstrip("\r\n")
    elif allow_config_password:
        resolved_password = config_password
    elif stdin.isatty():
        resolved_password = getpass.getpass(prompt)
    else:
        raise ValueError(
            f"{option_name}, {option_name}-stdin, or --allow-config-password is required"
        )

    if not resolved_password and not allow_empty:
        raise ValueError(f"{option_name} must not be empty")
    return resolved_password


DEFAULT_CREDENTIAL_PLACEHOLDER = "CHANGE_ME"


def reject_default_credential(value: str | None, *, env_var: str) -> str:
    """Raise when a credential was never set to a real value.

    A holder that still carries its dataclass default, or the literal
    placeholder copied verbatim from ``.env.example``, is indistinguishable
    from "nobody configured this" - so both are rejected here rather than
    silently generating a service that is reachable with a known password.
    """

    if not value or value == DEFAULT_CREDENTIAL_PLACEHOLDER:
        raise ValueError(
            f"{env_var} is not set. Set {env_var} to a real value before "
            f"generating this service; {DEFAULT_CREDENTIAL_PLACEHOLDER!r} is "
            "a non-functional placeholder."
        )
    return value


CommandRunner = Callable[..., subprocess.CompletedProcess]


def mask_secret(text: str, secrets: Iterable[str | None]) -> str:
    """Mask all non-empty secrets in text."""

    masked = text
    for secret in secrets:
        if secret:
            masked = masked.replace(secret, "***")
    return masked


@contextmanager
def secret_env_file(
    env_var: str,
    secret: str | None,
    *,
    prefix: str = "repom-secret-",
) -> Iterator[str | None]:
    """Yield a 0600 temp file path holding one ``env_var=secret`` line, or None.

    Pass the path to ``docker exec --env-file`` so the container reads the
    secret from the file's contents instead of the value appearing as a
    docker exec argument or on the host process environment. The file is
    removed as soon as the caller is done with it, keeping the window in
    which the secret exists on disk as short as possible.
    """

    if not secret:
        yield None
        return

    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".env")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w") as handle:
            handle.write(f"{env_var}={secret}\n")
        yield path
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def run_masked_command(
    command: Sequence[str],
    *,
    runner: CommandRunner,
    secrets: Iterable[str | None],
    error_type: type[Exception],
    action: str,
    input: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a command, raising ``error_type`` with masked output on failure.

    The command always runs with ``check=False, capture_output=True,
    text=True`` so a failing step never raises a raw ``CalledProcessError``
    with unmasked stderr; ``error_type`` is raised instead with the command,
    exit code, and stderr masked.
    """

    kwargs: dict[str, object] = {"check": False, "capture_output": True, "text": True}
    if input is not None:
        kwargs["input"] = input
    completed = runner(command, **kwargs)
    if completed.returncode != 0:
        raise error_type(
            mask_secret(
                f"{action} failed (exit {completed.returncode}): "
                f"command={' '.join(command)} stderr={completed.stderr}",
                secrets,
            )
        )
    return completed
