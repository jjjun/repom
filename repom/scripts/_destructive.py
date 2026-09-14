"""Shared confirmation guard for scripts that drop database state."""

from __future__ import annotations

import sys
from typing import TextIO


def confirm_destructive_operation(
    *,
    operation: str,
    target: str,
    exec_env: str,
    yes: bool,
    stdin: TextIO | None = None,
) -> None:
    """Refuse a destructive operation without confirmation or in prod.

    Raises SystemExit(1) when ``exec_env`` is ``"prod"`` - unconditionally, so
    neither an interactive answer nor ``--yes`` can override it - or when the
    caller has not confirmed: an interactive ``y`` on a TTY ``stdin``, or
    ``yes=True`` when stdin is not a TTY. ``target`` is printed as part of the
    prompt/refusal, so callers must mask it first (see safe_db_url()).
    """
    stdin = stdin if stdin is not None else sys.stdin

    if exec_env == "prod":
        print(f"Refusing to {operation} in EXEC_ENV=prod: {target}")
        raise SystemExit(1)

    print(f"About to {operation}: {target}")

    if stdin.isatty():
        confirm = input("Type 'y' to confirm: ").strip().lower()
        if confirm != "y":
            print(f"{operation.capitalize()} cancelled")
            raise SystemExit(1)
        return

    if not yes:
        print(f"Refusing to {operation} without --yes (stdin is not a TTY): {target}")
        raise SystemExit(1)
