import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

ASYNC_EXTRA_DRIVERS = {
    "async": {"aiosqlite"},
    "postgres-async": {"asyncpg"},
    "async-all": {"aiosqlite", "asyncpg"},
}


def _load_project_metadata() -> dict:
    pyproject_path = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)["project"]


def _requirement_names(requirements: list[str]) -> set[str]:
    return {Requirement(req).name for req in requirements}


def test_core_dependencies_require_sqlalchemy_asyncio():
    dependencies = _load_project_metadata()["dependencies"]

    sqlalchemy_requirements = [
        Requirement(req) for req in dependencies if Requirement(req).name == "sqlalchemy"
    ]

    assert len(sqlalchemy_requirements) == 1
    assert "asyncio" in sqlalchemy_requirements[0].extras


@pytest.mark.parametrize("extra", ASYNC_EXTRA_DRIVERS)
def test_async_extras_keep_their_drivers(extra):
    extra_requirements = _load_project_metadata()["optional-dependencies"][extra]

    assert ASYNC_EXTRA_DRIVERS[extra] <= _requirement_names(extra_requirements)
