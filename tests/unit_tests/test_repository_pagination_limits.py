"""
set_find_option() の offset / limit バリデーションのテスト

負値、bool、max_limit を超える値を拒否すること、および limit 未指定時の
挙動（全件取得 + RuntimeWarning）を確認します。
"""
from tests._init import *
from unittest.mock import patch
import sys
import warnings

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
import pytest
from repom.models.base_model import BaseModel
from repom import BaseRepository


class PaginationLimitModel(BaseModel):
    __tablename__ = 'pagination_limit_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class PaginationLimitRepository(BaseRepository[PaginationLimitModel]):
    def __init__(self, session):
        super().__init__(PaginationLimitModel, session)


@pytest.fixture
def seeded_repo(db_test):
    repo = PaginationLimitRepository(session=db_test)
    repo.saves([PaginationLimitModel(value=i) for i in range(5)])
    return repo


def test_negative_limit_raises(seeded_repo):
    with pytest.raises(ValueError, match="limit must not be negative"):
        seeded_repo.find(limit=-1)


def test_negative_offset_raises(seeded_repo):
    with pytest.raises(ValueError, match="offset must not be negative"):
        seeded_repo.find(offset=-1)


def test_bool_limit_raises(seeded_repo):
    with pytest.raises(TypeError, match="limit must be an integer"):
        seeded_repo.find(limit=True)


def test_bool_offset_raises(seeded_repo):
    with pytest.raises(TypeError, match="offset must be an integer"):
        seeded_repo.find(offset=False)


def test_limit_above_max_raises(db_test):
    class LowMaxLimitRepository(BaseRepository[PaginationLimitModel]):
        max_limit = 100

        def __init__(self, session):
            super().__init__(PaginationLimitModel, session)

    repo = LowMaxLimitRepository(session=db_test)

    with pytest.raises(ValueError, match="limit must not exceed max_limit"):
        repo.find(limit=101)


def test_limit_equal_to_max_limit_is_allowed(db_test):
    class LowMaxLimitRepository(BaseRepository[PaginationLimitModel]):
        max_limit = 100

        def __init__(self, session):
            super().__init__(PaginationLimitModel, session)

    repo = LowMaxLimitRepository(session=db_test)
    repo.saves([PaginationLimitModel(value=i) for i in range(3)])

    results = repo.find(limit=100)

    assert len(results) == 3


def test_max_limit_is_configurable_per_repository(db_test):
    """サブクラスで max_limit を引き上げれば、その値まで許可されることを確認"""
    class HighMaxLimitRepository(BaseRepository[PaginationLimitModel]):
        max_limit = 5000

        def __init__(self, session):
            super().__init__(PaginationLimitModel, session)

    repo = HighMaxLimitRepository(session=db_test)
    repo.saves([PaginationLimitModel(value=i) for i in range(3)])

    # デフォルトの max_limit (1000) を超えるが、このリポジトリでは許可される
    results = repo.find(limit=2000)

    assert len(results) == 3


def test_default_max_limit_is_1000():
    """未設定時の max_limit は保守的な既定値 (1000) であることを確認"""
    assert BaseRepository.max_limit == 1000


def test_max_limit_can_be_disabled(db_test):
    """max_limit を None にすると上限チェックが無効化されることを確認"""
    class UnboundedRepository(BaseRepository[PaginationLimitModel]):
        max_limit = None

        def __init__(self, session):
            super().__init__(PaginationLimitModel, session)

    repo = UnboundedRepository(session=db_test)
    repo.saves([PaginationLimitModel(value=i) for i in range(3)])

    results = repo.find(limit=10_000_000)

    assert len(results) == 3


def test_zero_limit_and_offset_are_allowed(seeded_repo):
    results = seeded_repo.find(limit=0)
    assert results == []

    results = seeded_repo.find(offset=0, limit=5)
    assert len(results) == 5


def test_omitted_limit_returns_all_rows_and_logs_warning(seeded_repo):
    """limit 省略時は従来どおり全件取得するが、RuntimeWarning で可視化されることを確認"""
    with pytest.warns(RuntimeWarning, match="without a limit"):
        results = seeded_repo.find()

    assert len(results) == 5


def test_omitted_limit_warning_points_to_caller(seeded_repo):
    """find() の RuntimeWarning が呼び出し元のファイル・行を指すことを確認
    （_find_with_filters() への委譲後も stacklevel=2 が維持されていることの回帰ガード、repom#161）"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        seeded_repo.find(); expected_lineno = sys._getframe().f_lineno  # noqa: E702

    assert len(caught) == 1
    assert caught[0].filename == __file__
    assert caught[0].lineno == expected_lineno


def test_sqlite_negative_limit_does_not_return_all_rows(seeded_repo):
    """SQLite が負の LIMIT を無制限として扱う前にクエリが拒否され、
    session.execute まで到達しないことを確認する（backend 差異の回帰ガード）"""
    with patch.object(seeded_repo.session, "execute", wraps=seeded_repo.session.execute) as mock_execute:
        with pytest.raises(ValueError):
            seeded_repo.find(limit=-1)

    mock_execute.assert_not_called()
