import pytest
from docs.pytest.sample_スコープ.sample5_6_module import SharedData

def test_check_data():
    assert 'test1' in SharedData.get_data()
