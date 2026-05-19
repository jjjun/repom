"""Behavior tests for circular import discovery patterns."""

import sys

from sqlalchemy.orm import class_mapper, clear_mappers, configure_mappers

from basekit.discovery import import_package_directory
from repom.models.base_model import Base


def _clear_circular_import_modules() -> None:
    for key in list(sys.modules.keys()):
        if "tests.fixtures.circular_import" in key:
            del sys.modules[key]


class TestSolution1DeferredMapperConfiguration:
    def test_deferred_mapper_configuration(self):
        Base.metadata.clear()
        clear_mappers()
        _clear_circular_import_modules()

        try:
            for package_name in [
                "tests.fixtures.circular_import.package_a",
                "tests.fixtures.circular_import.package_b",
            ]:
                failures = import_package_directory(
                    package_name=package_name,
                    excluded_dirs=set(),
                    allowed_prefixes={"tests.fixtures.", "repom."},
                )
                assert failures == []

            configure_mappers()

            from tests.fixtures.circular_import.package_a.model_a import ModelA
            from tests.fixtures.circular_import.package_b.model_b import ModelB

            assert class_mapper(ModelA) is not None
            assert class_mapper(ModelB) is not None
        finally:
            Base.metadata.clear()
            clear_mappers()
            _clear_circular_import_modules()

    def test_import_helper_can_collect_failures_without_raising(self):
        failures = import_package_directory(
            package_name="tests.fixtures.circular_import.missing_package",
            allowed_prefixes={"tests.fixtures.", "repom."},
            fail_on_error=False,
        )

        assert len(failures) == 1
        assert failures[0].target == "tests.fixtures.circular_import.missing_package"
