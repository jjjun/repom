import re
import tomllib
from pathlib import Path


def test_basekit_source_pins_an_immutable_commit():
    pyproject_path = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        source = tomllib.load(pyproject_file)["tool"]["uv"]["sources"]["basekit"]

    assert re.fullmatch(r"[0-9a-f]{40}", source["rev"])
    assert "branch" not in source
    assert "tag" not in source
