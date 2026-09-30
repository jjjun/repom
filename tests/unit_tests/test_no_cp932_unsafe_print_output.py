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

import pytest

from tests.source_policy import REPOM_ROOT, iter_repom_sources


def _is_cp932_unsafe(text: str) -> bool:
    try:
        text.encode("cp932")
    except UnicodeEncodeError:
        return True
    return False


def _string_literal_parts(node: ast.expr):
    """Yield static string parts of an output expression.

    This covers f-string segments, ``str.format()`` templates and arguments,
    and string concatenation. Runtime values that are not literals cannot be
    checked statically.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for value in node.values:
            yield from _string_literal_parts(value)
    elif isinstance(node, ast.FormattedValue):
        yield from _string_literal_parts(node.value)
        if node.format_spec is not None:
            yield from _string_literal_parts(node.format_spec)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        yield from _string_literal_parts(node.left)
        yield from _string_literal_parts(node.right)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "format":
            yield from _string_literal_parts(node.func.value)
            for argument in node.args:
                yield from _string_literal_parts(argument)
            for keyword in node.keywords:
                yield from _string_literal_parts(keyword.value)


def _cp932_unsafe_output_lines(source_path: Path, source: str) -> list[int]:
    tree = ast.parse(source, filename=str(source_path))
    offending_lines = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_print = isinstance(node.func, ast.Name) and node.func.id == "print"
        is_stdout_write = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "write"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "stdout"
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "sys"
        )
        if not (is_print or is_stdout_write):
            continue

        arguments = list(node.args) + [kw.value for kw in node.keywords]
        for argument in arguments:
            if any(_is_cp932_unsafe(part) for part in _string_literal_parts(argument)):
                offending_lines.append(node.lineno)
                break

    return offending_lines


def test_repom_standard_output_is_cp932_safe():
    violations = {}

    for source_path, source in iter_repom_sources():
        offending_lines = _cp932_unsafe_output_lines(source_path, source)
        if offending_lines:
            violations[str(source_path.relative_to(REPOM_ROOT))] = offending_lines

    assert not violations, (
        "print() and sys.stdout.write() calls must not contain characters unencodable in cp932 "
        "(the default stdout encoding on a Japanese Windows host) - replace "
        f"status symbols with the ASCII [OK]/[NG]/[WARN]/[INFO] markers: {violations}"
    )


@pytest.mark.parametrize(
    "source",
    [
        'print(f"unsafe: ⚠")',
        'print("unsafe: {}".format("⚠"))',
        'print("unsafe: " + "⚠")',
        'sys.stdout.write("unsafe: " + "⚠")',
    ],
)
def test_cp932_guard_detects_unsafe_output_forms(tmp_path, source):
    source_path = tmp_path / "output.py"

    assert _cp932_unsafe_output_lines(source_path, source) == [1]
