import pytest
from docs.pytest.sample_スコープ.sample5_6_module import SharedData


def test_add_data():
    SharedData.add_data('test1')
    assert 'test1' in SharedData.get_data()
