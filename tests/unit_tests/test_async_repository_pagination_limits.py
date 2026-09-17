"""
set_find_option() の offset / limit バリデーションの非同期版テスト

test_repository_pagination_limits.py の全テストケースを非同期版に変換したもの。
"""
from tests._init import *
from unittest.mock import patch
import sys
import warnings

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
import pytest
import pytest_asyncio
from repom.models.base_model import BaseModel
from repom import AsyncBaseRepository


class AsyncPaginationLimitModel(BaseModel):
    __tablename__ = 'async_pagination_limit_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class AsyncPaginationLimitRepository(AsyncBaseRepository[AsyncPaginationLimitModel]):
    def __init__(self, session):
        super().__init__(AsyncPaginationLimitModel, session)


@pytest_asyncio.fixture
async def seeded_repo(async_db_test):
    repo = AsyncPaginationLimitRepository(session=async_db_test)
    await repo.saves([AsyncPaginationLimitModel(value=i) for i in range(5)])
    return repo


@pytest.mark.asyncio
async def test_negative_limit_raises(seeded_repo):
    with pytest.raises(ValueError, match="limit must not be negative"):
        await seeded_repo.find(limit=-1)


@pytest.mark.asyncio
async def test_negative_offset_raises(seeded_repo):
    with pytest.raises(ValueError, match="offset must not be negative"):
        await seeded_repo.find(offset=-1)


@pytest.mark.asyncio
async def test_bool_limit_raises(seeded_repo):
    with pytest.raises(TypeError, match="limit must be an integer"):
        await seeded_repo.find(limit=True)


@pytest.mark.asyncio
async def test_bool_offset_raises(seeded_repo):
    with pytest.raises(TypeError, match="offset must be an integer"):
        await seeded_repo.find(offset=False)


@pytest.mark.asyncio
async def test_limit_above_max_raises(async_db_test):
    class LowMaxLimitRepository(AsyncBaseRepository[AsyncPaginationLimitModel]):
        max_limit = 100

        def __init__(self, session):
            super().__init__(AsyncPaginationLimitModel, session)

    repo = LowMaxLimitRepository(session=async_db_test)

    with pytest.raises(ValueError, match="limit must not exceed max_limit"):
        await repo.find(limit=101)


@pytest.mark.asyncio
async def test_limit_equal_to_max_limit_is_allowed(async_db_test):
    class LowMaxLimitRepository(AsyncBaseRepository[AsyncPaginationLimitModel]):
        max_limit = 100

        def __init__(self, session):
            super().__init__(AsyncPaginationLimitModel, session)

    repo = LowMaxLimitRepository(session=async_db_test)
    await repo.saves([AsyncPaginationLimitModel(value=i) for i in range(3)])

    results = await repo.find(limit=100)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_max_limit_is_configurable_per_repository(async_db_test):
    """サブクラスで max_limit を引き上げれば、その値まで許可されることを確認"""
    class HighMaxLimitRepository(AsyncBaseRepository[AsyncPaginationLimitModel]):
        max_limit = 5000

        def __init__(self, session):
            super().__init__(AsyncPaginationLimitModel, session)

    repo = HighMaxLimitRepository(session=async_db_test)
    await repo.saves([AsyncPaginationLimitModel(value=i) for i in range(3)])

    results = await repo.find(limit=2000)

    assert len(results) == 3


def test_default_max_limit_is_1000():
    """未設定時の max_limit は保守的な既定値 (1000) であることを確認"""
    assert AsyncBaseRepository.max_limit == 1000


@pytest.mark.asyncio
async def test_max_limit_can_be_disabled(async_db_test):
    """max_limit を None にすると上限チェックが無効化されることを確認"""
    class UnboundedRepository(AsyncBaseRepository[AsyncPaginationLimitModel]):
        max_limit = None

        def __init__(self, session):
            super().__init__(AsyncPaginationLimitModel, session)

    repo = UnboundedRepository(session=async_db_test)
    await repo.saves([AsyncPaginationLimitModel(value=i) for i in range(3)])

    results = await repo.find(limit=10_000_000)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_zero_limit_and_offset_are_allowed(seeded_repo):
    results = await seeded_repo.find(limit=0)
    assert results == []

    results = await seeded_repo.find(offset=0, limit=5)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_omitted_limit_returns_all_rows_and_logs_warning(seeded_repo):
    """limit 省略時は従来どおり全件取得するが、RuntimeWarning で可視化されることを確認"""
    with pytest.warns(RuntimeWarning, match="without a limit"):
        results = await seeded_repo.find()

    assert len(results) == 5


@pytest.mark.asyncio
async def test_omitted_limit_warning_points_to_caller(seeded_repo):
    """find() の RuntimeWarning が呼び出し元のファイル・行を指すことを確認
    （_find_with_filters() への委譲後も stacklevel=2 が維持されていることの回帰ガード、repom#161）"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await seeded_repo.find(); expected_lineno = sys._getframe().f_lineno  # noqa: E702

    assert len(caught) == 1
    assert caught[0].filename == __file__
    assert caught[0].lineno == expected_lineno


@pytest.mark.asyncio
async def test_sqlite_negative_limit_does_not_return_all_rows(seeded_repo):
    """SQLite が負の LIMIT を無制限として扱う前にクエリが拒否され、
    session.execute まで到達しないことを確認する（backend 差異の回帰ガード）"""
    with patch.object(seeded_repo.session, "execute", wraps=seeded_repo.session.execute) as mock_execute:
        with pytest.raises(ValueError):
            await seeded_repo.find(limit=-1)

    mock_execute.assert_not_called()
