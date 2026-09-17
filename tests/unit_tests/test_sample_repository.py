"""SampleRepository のテスト

session を省略した場合に BaseRepository の内部セッション機構
（_session_scope() -> get_db_session()）が正しく使われることを確認します。
"""

from repom.examples.repositories.sample import SampleRepository


def test_sample_repository_default_session_find():
    repo = SampleRepository()
    results = repo.find(limit=1)
    assert isinstance(results, list)


def test_sample_repository_explicit_none_session_find():
    repo = SampleRepository(session=None)
    results = repo.find(limit=1)
    assert isinstance(results, list)
