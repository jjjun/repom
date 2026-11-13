import tomllib
from pathlib import Path

import pytest

ASYNC_EXTRAS = ["async", "postgres-async", "async-all"]


def _load_project_metadata() -> dict:
    pyproject_path = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)["project"]


def _core_sqlalchemy_specifier(dependencies: list[str]) -> str:
    matches = [req for req in dependencies if req.startswith("sqlalchemy")]
    assert len(matches) == 1, f"expected one sqlalchemy requirement, got {matches}"
    return matches[0][len("sqlalchemy"):]


@pytest.mark.parametrize("extra", ASYNC_EXTRAS)
def test_async_extras_require_sqlalchemy_asyncio(extra):
    project = _load_project_metadata()
    core_specifier = _core_sqlalchemy_specifier(project["dependencies"])

    extra_requirements = project["optional-dependencies"][extra]

    assert f"sqlalchemy[asyncio]{core_specifier}" in extra_requirements


def test_core_dependencies_do_not_require_greenlet():
    dependencies = _load_project_metadata()["dependencies"]

    assert not any(req.startswith("greenlet") for req in dependencies)
    assert not any("[asyncio]" in req for req in dependencies)
