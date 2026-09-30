"""Guard test: exception messages must never embed a raw, unmasked DSN.

A ``raise`` statement that f-string-interpolates a bare url/dsn-like
variable directly (e.g. ``raise ValueError(f"... {sync_url}")``) puts the
full connection string - password included - into the exception message,
which downstream code may log, report to an error tracker, or return in an
HTTP error body. Route such a variable through ``safe_db_url()`` (or another
masking helper) before it reaches a ``raise``.

This walks every module under repom/ with an AST parse (rather than
importing modules or grepping text), so a lazy, function-level raise is
caught just as reliably as a module-level one.
"""

import ast
from pathlib import Path

import pytest

from tests.source_policy import REPOM_ROOT, iter_repom_sources

# Common names used for a raw connection string/DSN in this codebase.
FORBIDDEN_NAMES = ("url", "dsn", "sync_url", "async_url", "db_url")

def _contains_raw_dsn(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in FORBIDDEN_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in FORBIDDEN_NAMES or _contains_raw_dsn(node.value)
    if isinstance(node, ast.Call):
        function_name = (
            node.func.id if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute)
            else None
        )
        if function_name == "safe_db_url":
            return False
    return any(_contains_raw_dsn(child) for child in ast.iter_child_nodes(node))


def _raw_dsn_raise_lines(source_path: Path, source: str) -> list[int]:
    tree = ast.parse(source, filename=str(source_path))
    offending_lines = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None and _contains_raw_dsn(node.exc):
            offending_lines.append(node.lineno)

    return offending_lines


def test_repom_never_interpolates_a_raw_dsn_into_raise_messages():
    violations = {}

    for source_path, source in iter_repom_sources():
        offending_lines = _raw_dsn_raise_lines(source_path, source)
        if offending_lines:
            violations[str(source_path.relative_to(REPOM_ROOT))] = offending_lines

    assert not violations, (
        "raise statements must not interpolate a raw url/dsn variable "
        f"directly; wrap it in safe_db_url() first: {violations}"
    )


@pytest.mark.parametrize(
    "source",
    [
        'raise ValueError(f"could not connect to {db_url}")',
        'raise ValueError("could not connect to {}".format(config.db_url))',
        'raise ValueError("could not connect to " + config.db_url)',
        'raise ValueError(config.db_url)',
    ],
)
def test_raw_dsn_guard_detects_raise_message_forms(tmp_path, source):
    source_path = tmp_path / "raise_message.py"

    assert _raw_dsn_raise_lines(source_path, source) == [1]


def test_raw_dsn_guard_allows_safe_db_url_masking(tmp_path):
    source_path = tmp_path / "raise_message.py"
    source = 'raise ValueError(f"could not connect to {safe_db_url(config.db_url)}")'

    assert _raw_dsn_raise_lines(source_path, source) == []
