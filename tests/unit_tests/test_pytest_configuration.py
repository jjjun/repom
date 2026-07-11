import tomllib
from pathlib import Path


def test_project_defaults_do_not_override_quiet_or_capture_options():
    pyproject_path = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        addopts = tomllib.load(pyproject_file)["tool"]["pytest"]["ini_options"]["addopts"]

    assert not any(option.startswith("-v") for option in addopts)
    assert not any(option == "--capture=tee-sys" for option in addopts)
