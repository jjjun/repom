"""Shared Alembic location constants."""

from pathlib import Path

SCRIPT_LOCATION = "repom:alembic"


def script_location_path() -> Path:
    """Return the filesystem directory containing repom's Alembic resources."""
    return Path(__file__).resolve().parent
