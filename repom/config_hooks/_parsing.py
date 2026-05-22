"""Parsing helpers for runtime config hook environment overrides."""

from __future__ import annotations


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def parse_bool_env(name: str, value: str) -> bool:
    """Parse a boolean environment variable value."""
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value")


def parse_int_env(name: str, value: str) -> int:
    """Parse an integer environment variable value."""
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def parse_port_env(name: str, value: str) -> int:
    """Parse a TCP port environment variable value."""
    port = parse_int_env(name, value)
    if not (0 < port < 65536):
        raise ValueError(f"{name} must be between 1 and 65535")
    return port


__all__ = [
    "FALSE_VALUES",
    "TRUE_VALUES",
    "parse_bool_env",
    "parse_int_env",
    "parse_port_env",
]
