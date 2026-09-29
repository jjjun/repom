"""Behavior tests for circular import discovery patterns."""

from basekit.discovery import import_package_directory
from tests.behavior_tests.test_circular_import import _run_isolated_python


class TestSolution1DeferredMapperConfiguration:
    def test_deferred_mapper_configuration(self):
        result = _run_isolated_python(
            """
from basekit.discovery import import_package_directory
from sqlalchemy.orm import class_mapper, configure_mappers

for package_name in (
    "tests.fixtures.circular_import.package_a",
    "tests.fixtures.circular_import.package_b",
):
    failures = import_package_directory(
        package_name=package_name,
        excluded_dirs=set(),
        allowed_prefixes={"tests.fixtures.", "tests.behavior_tests.", "repom."},
    )
    assert failures == []

configure_mappers()

from tests.fixtures.circular_import.package_a.model_a import ModelA
from tests.fixtures.circular_import.package_b.model_b import ModelB

assert class_mapper(ModelA) is not None
assert class_mapper(ModelB) is not None
"""
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_import_helper_can_collect_failures_without_raising(self):
        failures = import_package_directory(
            package_name="tests.fixtures.circular_import.missing_package",
            allowed_prefixes={"tests.fixtures.", "repom."},
            fail_on_error=False,
        )

        assert len(failures) == 1
        assert failures[0].target == "tests.fixtures.circular_import.missing_package"
