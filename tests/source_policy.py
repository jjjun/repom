"""Shared source traversal for package policy tests."""

from collections.abc import Iterator
from pathlib import Path

import repom

REPOM_ROOT = Path(repom.__file__).parent


def iter_repom_sources() -> Iterator[tuple[Path, str]]:
    for source_path in sorted(REPOM_ROOT.rglob("*.py")):
        yield source_path, source_path.read_text(encoding="utf-8")
