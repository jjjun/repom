"""

Behavior coverage for circular SQLAlchemy mapper initialization.

Issue history is stored in issuekit; this file is the executable regression
specification.
"""
import pytest
from repom.models.base_model import Base
from sqlalchemy.orm import clear_mappers


@pytest.fixture
def clean_circular_import_env():
    """

    
    - Base.metadata 
    - SQLAlchemy 
    - ests.fixtures.circular_import

    
    """
    # 
    Base.metadata.clear()
    clear_mappers()

    import sys
    for key in list(sys.modules.keys()):
        if 'tests.fixtures.circular_import' in key:
            del sys.modules[key]

    yield  # 

    # 
    Base.metadata.clear()
    clear_mappers()

    for key in list(sys.modules.keys()):
        if 'tests.fixtures.circular_import' in key:
            del sys.modules[key]


class TestCircularImportIssue:
    """Issue #020: 

    
    1. 
    2. 

    
    mine-py mport_from_packages 
    fail_on_error=False 
    
    
    """

    def test_reproduce_circular_import_error(self, clean_circular_import_env):
        """

        ackage_a onfigure_mappers() 
        odelB 
        ssue #020 

        
        - ModelA  ModelB 
        - ModelB 
        -  'ModelB' 
        """
        from basekit.discovery import import_package_directory
        from sqlalchemy.orm import configure_mappers

        # package_a 
        import_package_directory(
            package_name='tests.fixtures.circular_import.package_a',
            excluded_dirs=set(),
            allowed_prefixes={'tests.fixtures.', 'repom.'}
        )

        # 
        with pytest.raises(Exception) as exc_info:
            configure_mappers()

        # 
        error_message = str(exc_info.value)
        assert "failed to locate a name" in error_message.lower(), (
            f"Expected 'failed to locate a name' in error: {error_message}"
        )
        assert "'ModelB'" in error_message, (
            f"Expected 'ModelB' in error: {error_message}"
        )

    def test_verify_deferred_mapper_solution(self, clean_circular_import_env):
        """

        onfigure_mappers() 
        
        ssue #020 

        
        - configure_mappers() 
        - 
        - 

        
        """
        from basekit.discovery import import_package_directory
        from sqlalchemy.orm import class_mapper

        # 
        import_package_directory(
            package_name='tests.fixtures.circular_import.package_a',
            excluded_dirs=set(),
            allowed_prefixes={'tests.fixtures.', 'repom.'}
        )

        import_package_directory(
            package_name='tests.fixtures.circular_import.package_b',
            excluded_dirs=set(),
            allowed_prefixes={'tests.fixtures.', 'repom.'}
        )

        # configure_mappers() 

        # 
        from tests.fixtures.circular_import.package_a.model_a import ModelA
        from tests.fixtures.circular_import.package_b.model_b import ModelB

        # 
        assert hasattr(ModelA, 'children'), "ModelA should have 'children' relationship"
        assert hasattr(ModelB, 'parent'), "ModelB should have 'parent' relationship"

        # 
        mapper_a = class_mapper(ModelA)
        mapper_b = class_mapper(ModelB)

        assert mapper_a is not None, "ModelA mapper should be initialized"
        assert mapper_b is not None, "ModelB mapper should be initialized"

        # 
        tables = list(Base.metadata.tables.keys())
        assert 'test_model_a' in tables, "test_model_a should be registered"
        assert 'test_model_b' in tables, "test_model_b should be registered"


