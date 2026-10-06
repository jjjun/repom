"""Safety helpers for hand-built Docker Compose artifacts.

``basekit.docker_compose`` renders ``DockerService``/``DockerVolume`` fields
into YAML lines with plain ``f"{key}: {value}"`` interpolation and no
escaping (see ``docs/guides/features/docker_manager_guide.md`` for the
ownership boundary between basekit and repom). repom controls the values
handed to that generator, so every value that reaches a Compose environment
block, a healthcheck, or a generated secrets file must be validated and
quoted here first.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

LOOPBACK_HOST = "127.0.0.1"
_ALL_INTERFACES_HOST = "0.0.0.0"

_FORBIDDEN_CHARACTERS = {
    "\n": "a newline",
    "\r": "a carriage return",
    "\x00": "a NUL byte",
}
_DOCKER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_DOCKER_IMAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@${}-]*$")
_RESTART_POLICY_PATTERN = re.compile(r"on-failure:([0-9]+)")


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


def validate_docker_name(value: str, *, field_name: str) -> str:
    """Validate a container or named-volume scalar before Compose rendering."""
    reject_control_characters(value, field_name=field_name)
    if not _DOCKER_NAME_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a Docker name containing only letters, "
            "digits, '.', '_' or '-' and starting with a letter or digit"
        )
    return value


def validate_restart_policy(value: str, *, field_name: str) -> str:
    """Validate a Docker container restart policy before Compose rendering."""

    if isinstance(value, str) and value in {
        "no",
        "always",
        "unless-stopped",
        "on-failure",
    }:
        return value
    match = _RESTART_POLICY_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match is not None and int(match.group(1)) > 0:
        return value
    raise ValueError(
        f"{field_name} must be 'no', 'always', 'unless-stopped', 'on-failure', "
        "or 'on-failure:<positive integer>'"
    )


def validate_docker_image(value: str, *, field_name: str) -> str:
    """Reject image references that can break out of a plain Compose scalar."""
    reject_control_characters(value, field_name=field_name)
    if not _DOCKER_IMAGE_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a single-line Docker image reference "
            "starting with a letter or digit"
        )
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


def parse_env_file(content: str) -> dict[str, str]:
    """Parse the quoted format emitted by :func:`format_env_file`."""

    values: dict[str, str] = {}
    lines = content.split("\n")
    if lines[-1] == "":
        lines.pop()
    for line_number, line in enumerate(lines, start=1):
        if not line or "=" not in line:
            raise ValueError(f"Invalid generated .env entry on line {line_number}")
        key, encoded_value = line.split("=", maxsplit=1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None:
            raise ValueError(f"Invalid generated .env key on line {line_number}")
        if not encoded_value.startswith('"') or not encoded_value.endswith('"'):
            raise ValueError(f"Invalid generated .env value on line {line_number}")

        encoded_value = encoded_value[1:-1]
        decoded = []
        index = 0
        while index < len(encoded_value):
            character = encoded_value[index]
            if character == "\\":
                index += 1
                if index >= len(encoded_value) or encoded_value[index] not in {'\\', '"'}:
                    raise ValueError(
                        f"Invalid generated .env escape on line {line_number}"
                    )
                decoded.append(encoded_value[index])
            elif character == "$":
                index += 1
                if index >= len(encoded_value) or encoded_value[index] != "$":
                    raise ValueError(
                        f"Invalid generated .env dollar escape on line {line_number}"
                    )
                decoded.append("$")
            elif character == '"':
                raise ValueError(f"Invalid generated .env quote on line {line_number}")
            else:
                decoded.append(character)
            index += 1

        if key in values:
            raise ValueError(f"Duplicate generated .env key on line {line_number}")
        decoded_value = "".join(decoded)
        reject_control_characters(decoded_value, field_name=key)
        values[key] = decoded_value
    return values


def validate_stored_secret_values(
    path: Path,
    current_values: Mapping[str, str | None],
    *,
    default_credential_placeholder: str,
    rotation_commands: tuple[str, ...],
    generate_command: str,
) -> None:
    """Keep an existing generated ``.env`` authoritative during auto-start."""

    try:
        stored_values = parse_env_file(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(
            f"Cannot safely read stored credentials from {path}. Run "
            f"{generate_command} --force-regenerate or restore {path}.bak."
        ) from exc
    commands = ", ".join(rotation_commands)
    for key, current_value in current_values.items():
        if key not in stored_values:
            raise ValueError(
                f"Refusing to auto-start because {path} does not contain the "
                f"required {key} entry. Use {commands} to rotate credentials, "
                f"or {generate_command} --force-regenerate to regenerate it."
            )
        if (
            current_value
            and current_value != default_credential_placeholder
            and current_value != stored_values[key]
        ):
            raise ValueError(
                f"Refusing to auto-start because credentials in {path} differ "
                f"from the current configuration. Use {commands} to rotate "
                f"credentials, or {generate_command} --force-regenerate to "
                "intentionally replace them."
            )


def write_secret_file(path: Path, content: str) -> None:
    """Write plaintext secrets owner-only, backing up changed prior content."""

    if path.exists():
        backup_secret_file(path, content)
    _write_secret_file_atomically(path, content)


def _write_secret_file_atomically(path: Path, content: str) -> None:
    """Write through a restrictive sibling temporary file, then replace path."""

    file_descriptor, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        temp_file = os.fdopen(file_descriptor, "w", encoding="utf-8")
    except BaseException:
        try:
            os.close(file_descriptor)
        except OSError:
            pass
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise

    try:
        with temp_file:
            temp_file.write(content)
        os.replace(temp_path, path)
    except BaseException:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


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
    _write_secret_file_atomically(backup_path, previous_content)


__all__ = [
    "LOOPBACK_HOST",
    "format_bound_port",
    "format_env_file",
    "parse_env_file",
    "quote_yaml_string",
    "reject_control_characters",
    "backup_secret_file",
    "validate_secret_file_overwrite",
    "validate_stored_secret_values",
    "validate_docker_image",
    "validate_docker_name",
    "validate_restart_policy",
    "write_secret_file",
]
