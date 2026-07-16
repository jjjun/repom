import tomllib
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace


_debug_logging_enabled = run_path(
    str(Path(__file__).parents[1] / "conftest.py")
)["_debug_logging_enabled"]


def test_project_defaults_do_not_override_quiet_or_capture_options():
    pyproject_path = Path(__file__).parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        addopts = tomllib.load(pyproject_file)["tool"]["pytest"]["ini_options"]["addopts"]

    assert not any(option.startswith("-v") for option in addopts)
    assert not any(option == "--capture=tee-sys" for option in addopts)


def test_double_verbose_enables_debug_logging_after_quiet_default():
    config = SimpleNamespace(option=SimpleNamespace(verbose=1))

    assert _debug_logging_enabled(config)


def test_default_quiet_run_does_not_enable_debug_logging():
    config = SimpleNamespace(option=SimpleNamespace(verbose=-1))

    assert not _debug_logging_enabled(config)
