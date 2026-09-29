import pytest

from repom.database import Base
from tests.behavior_tests.isolated_models import clear_behavior_models


@pytest.fixture(autouse=True)
def clean_behavior_models():
    existing_tables = set(Base.metadata.tables)
    yield
    clear_behavior_models()
    for key, table in tuple(Base.metadata.tables.items()):
        if key not in existing_tables:
            Base.metadata.remove(table)
