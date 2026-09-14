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
import re
from pathlib import Path

import repom

REPOM_ROOT = Path(repom.__file__).parent

# Common names used for a raw connection string/DSN in this codebase.
FORBIDDEN_NAMES = ("url", "dsn", "sync_url", "async_url", "db_url")

# Matches a bare f-string interpolation of one of the forbidden names, e.g.
# "{url}", "{ url }", "{dsn!r}", "{sync_url:>10}" - but not
# "{safe_db_url(sync_url)}", since something other than the bare name
# immediately follows the opening brace there.
_BARE_INTERPOLATION_RE = re.compile(
    r"\{\s*(?:" + "|".join(FORBIDDEN_NAMES) + r")\s*[!:}]"
)


def _iter_repom_source_files():
    return sorted(REPOM_ROOT.rglob("*.py"))


def _raw_dsn_raise_lines(source_path: Path) -> list[int]:
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    offending_lines = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        segment = ast.get_source_segment(source, node)
        if segment and _BARE_INTERPOLATION_RE.search(segment):
            offending_lines.append(node.lineno)

    return offending_lines


def test_repom_never_interpolates_a_raw_dsn_into_raise_messages():
    violations = {}

    for source_path in _iter_repom_source_files():
        offending_lines = _raw_dsn_raise_lines(source_path)
        if offending_lines:
            violations[str(source_path.relative_to(REPOM_ROOT))] = offending_lines

    assert not violations, (
        "raise statements must not interpolate a raw url/dsn variable "
        f"directly; wrap it in safe_db_url() first: {violations}"
    )
