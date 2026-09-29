"""Safety helpers for hand-built Docker Compose artifacts.

``basekit.docker_compose`` renders ``DockerService``/``DockerVolume`` fields
into YAML lines with plain ``f"{key}: {value}"`` interpolation and no
escaping (see ``docs/guides/features/docker_compose_guide.md`` for the
ownership boundary between basekit and repom). repom controls the values
handed to that generator, so every value that reaches a Compose environment
block, a healthcheck, or a generated secrets file must be validated and
quoted here first.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path

LOOPBACK_HOST = "127.0.0.1"
_ALL_INTERFACES_HOST = "0.0.0.0"

_FORBIDDEN_CHARACTERS = {
    "\n": "a newline",
    "\r": "a carriage return",
    "\x00": "a NUL byte",
}


def reject_control_characters(value: str, *, field_name: str) -> str:
    """Reject a value that could break out of a single YAML line or config line.

    Docker Compose environment values, container/volume names, and generated
    secret files (``.env``, ``redis.conf``) are each written as one line. A
    newline, carriage return, or NUL byte lets a value terminate that line
    early and inject unrelated YAML keys or config directives.
    """

    for character, description in _FORBIDDEN_CHARACTERS.items():
        if character in value:
            raise ValueError(f"{field_name} must not contain {description}")
    return value


def quote_yaml_string(value: str) -> str:
    """Render ``value`` as a YAML double-quoted scalar.

    Double-quoted is the only YAML scalar style that keeps arbitrary text
    (colons, ``#``, leading ``-``/``&``/``*`` indicators, or control
    characters escaped below) from being reinterpreted as a new node, a
    comment, or a new mapping key.
    """

    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\x00", "\\0")
    )
    return f'"{escaped}"'


def format_bound_port(host_port: int, container_port: int, *, expose_to_lan: bool) -> str:
    """Format a Compose port mapping, bound to loopback unless opted out."""

    bind_host = _ALL_INTERFACES_HOST if expose_to_lan else LOOPBACK_HOST
    return f"{bind_host}:{host_port}:{container_port}"


def format_env_file(values: Mapping[str, str]) -> str:
    """Render ``values`` as a Compose ``.env`` file, one double-quoted line each.

    Compose's env-file parser interpolates a bare or double-quoted ``$`` (only
    ``$$`` reads back as a literal dollar sign) and treats a ``#`` preceded by
    whitespace as the start of a comment, in both unquoted and double-quoted
    values. Doubling every literal ``$`` and wrapping the value in double
    quotes keeps a value such as ``pa$$w0rd #1`` intact instead of being
    partially interpolated or truncated at the comment marker.
    """

    lines = []
    for key, value in values.items():
        reject_control_characters(value, field_name=key)
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
        lines.append(f'{key}="{escaped}"')
    return "".join(f"{line}\n" for line in lines)


def write_secret_file(path: Path, content: str) -> None:
    """Write plaintext secrets owner-only, backing up changed prior content."""

    if path.exists():
        backup_secret_file(path, content)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def validate_secret_file_overwrite(
    path: Path,
    content: str,
    *,
    overwrite_secrets: bool,
    rotation_commands: tuple[str, ...],
) -> None:
    """Refuse to replace a generated secret file with different content."""

    if not path.exists() or path.read_text(encoding="utf-8") == content:
        return
    if overwrite_secrets:
        return

    commands = ", ".join(rotation_commands)
    raise ValueError(
        f"Refusing to overwrite {path} because its secrets differ from the "
        f"current configuration. Use {commands} to rotate credentials, or "
        "pass overwrite_secrets=True (CLI: --force-regenerate) to intentionally "
        "replace them."
    )


def backup_secret_file(path: Path, new_content: str) -> None:
    """Keep the changed prior content as an owner-only one-generation backup."""

    previous_content = path.read_text(encoding="utf-8")
    if previous_content == new_content:
        return

    backup_path = path.with_name(f"{path.name}.bak")
    backup_path.write_text(previous_content, encoding="utf-8")
    os.chmod(backup_path, stat.S_IRUSR | stat.S_IWUSR)


__all__ = [
    "LOOPBACK_HOST",
    "format_bound_port",
    "format_env_file",
    "quote_yaml_string",
    "reject_control_characters",
    "backup_secret_file",
    "validate_secret_file_overwrite",
    "write_secret_file",
]
