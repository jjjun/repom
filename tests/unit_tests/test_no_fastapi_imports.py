"""Guard test: repom must never import fastapi.

repom is a generic SQLAlchemy persistence package; FastAPI integration
belongs to the consuming framework (fast-domain). This test walks every
module under repom/ with an AST parse (rather than importing modules or
grepping text) so that a lazy, function-level `from fastapi import ...`
is caught just as reliably as a top-level one, and so that docstrings or
comments that merely mention fastapi don't cause false positives.
"""

import ast
from pathlib import Path

import repom

REPOM_ROOT = Path(repom.__file__).parent


def _iter_repom_source_files():
    return sorted(REPOM_ROOT.rglob("*.py"))


def _fastapi_import_lines(source_path: Path) -> list[int]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offending_lines = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "fastapi" or alias.name.startswith("fastapi.") for alias in node.names):
                offending_lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "fastapi" or node.module.startswith("fastapi.")):
                offending_lines.append(node.lineno)

    return offending_lines


def test_repom_package_never_imports_fastapi():
    violations = {}

    for source_path in _iter_repom_source_files():
        offending_lines = _fastapi_import_lines(source_path)
        if offending_lines:
            violations[str(source_path.relative_to(REPOM_ROOT))] = offending_lines

    assert not violations, (
        "repom/ must not import fastapi (FastAPI integration belongs to the "
        f"consuming framework): {violations}"
    )


def test_repom_no_longer_exports_removed_fastapi_bridge_names():
    removed_names = {"BaseModelAuto", "build_order_by_query_depends"}
    assert not removed_names & set(dir(repom))
    assert not removed_names & set(repom.__all__)
