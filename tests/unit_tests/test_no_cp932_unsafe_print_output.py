"""Guard test: print() output must stay encodable with cp932.

On a Japanese Windows host, redirecting stdout (a pipe, a file, a task
runner, CI logs, subprocess capture) makes Python fall back to the ANSI
code page cp932 unless the encoding is overridden. A status symbol such as
a check mark, cross, or emoji cannot be encoded there and raises
UnicodeEncodeError mid-script - sometimes after the destructive work has
already happened (see repom/alembic/reset.py's version-table drop and
migration-file deletion). Use the existing ASCII markers instead
([OK]/[NG]/[WARN]/[INFO]); Japanese message text is fine, since cp932
encodes it without trouble.

This walks every module under repom/ with an AST parse (rather than
importing modules or grepping text), so a lazily constructed message is
caught just as reliably as a top-level one.
"""

import ast
from pathlib import Path

import repom

REPOM_ROOT = Path(repom.__file__).parent


def _iter_repom_source_files():
    return sorted(REPOM_ROOT.rglob("*.py"))


def _is_cp932_unsafe(text: str) -> bool:
    try:
        text.encode("cp932")
    except UnicodeEncodeError:
        return True
    return False


def _string_literal_parts(node: ast.expr):
    """Yield the string literal parts of a print() argument.

    A plain string constant yields itself; an f-string yields only its
    literal segments, since the interpolated (FormattedValue) parts are
    runtime-dependent and can't be checked statically.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                yield value.value


def _cp932_unsafe_print_lines(source_path: Path) -> list[int]:
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    offending_lines = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "print"):
            continue

        arguments = list(node.args) + [kw.value for kw in node.keywords]
        for argument in arguments:
            if any(_is_cp932_unsafe(part) for part in _string_literal_parts(argument)):
                offending_lines.append(node.lineno)
                break

    return offending_lines


def test_repom_print_output_is_cp932_safe():
    violations = {}

    for source_path in _iter_repom_source_files():
        offending_lines = _cp932_unsafe_print_lines(source_path)
        if offending_lines:
            violations[str(source_path.relative_to(REPOM_ROOT))] = offending_lines

    assert not violations, (
        "print() calls must not contain characters unencodable in cp932 "
        "(the default stdout encoding on a Japanese Windows host) - replace "
        f"status symbols with the ASCII [OK]/[NG]/[WARN]/[INFO] markers: {violations}"
    )
