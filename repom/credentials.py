"""Shared password input helpers for credential rotation commands."""

from __future__ import annotations

import getpass
import sys
from typing import TextIO


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
