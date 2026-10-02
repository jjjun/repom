"""Pagination validation shared by the sync and async repositories."""
from unittest.mock import patch
import os
import sys
import warnings

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
import pytest
import pytest_asyncio

from repom.models.base_model import BaseModel


class PaginationLimitModel(BaseModel):
    __tablename__ = 'pagination_limit_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


@pytest_asyncio.fixture
async def seeded_repo(repository_adapter):
    repo = repository_adapter.repository_class(
        PaginationLimitModel,
        session=repository_adapter.session,
    )
    await repository_adapter.call(
        repo.saves,
        [PaginationLimitModel(value=i) for i in range(5)],
    )
    return repo


@pytest.mark.asyncio
async def test_negative_limit_raises(repository_adapter, seeded_repo):
    with pytest.raises(ValueError, match="limit must not be negative"):
        await repository_adapter.call(seeded_repo.find, limit=-1)


@pytest.mark.asyncio
async def test_negative_offset_raises(repository_adapter, seeded_repo):
    with pytest.raises(ValueError, match="offset must not be negative"):
        await repository_adapter.call(seeded_repo.find, offset=-1)


@pytest.mark.asyncio
async def test_bool_limit_raises(repository_adapter, seeded_repo):
    with pytest.raises(TypeError, match="limit must be an integer"):
        await repository_adapter.call(seeded_repo.find, limit=True)


@pytest.mark.asyncio
async def test_bool_offset_raises(repository_adapter, seeded_repo):
    with pytest.raises(TypeError, match="offset must be an integer"):
        await repository_adapter.call(seeded_repo.find, offset=False)


@pytest.mark.asyncio
async def test_limit_above_max_raises(repository_adapter, monkeypatch):
    repo = repository_adapter.repository_class(
        PaginationLimitModel,
        session=repository_adapter.session,
    )
    monkeypatch.setattr(repository_adapter.repository_class, 'max_limit', 100)

    with pytest.raises(ValueError, match="limit must not exceed max_limit"):
        await repository_adapter.call(repo.find, limit=101)


@pytest.mark.asyncio
async def test_limit_equal_to_max_limit_is_allowed(repository_adapter, monkeypatch):
    repo = repository_adapter.repository_class(
        PaginationLimitModel,
        session=repository_adapter.session,
    )
    monkeypatch.setattr(repository_adapter.repository_class, 'max_limit', 100)
    await repository_adapter.call(
        repo.saves,
        [PaginationLimitModel(value=i) for i in range(3)],
    )

    results = await repository_adapter.call(repo.find, limit=100)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_max_limit_is_configurable_per_repository(repository_adapter, monkeypatch):
    repo = repository_adapter.repository_class(
        PaginationLimitModel,
        session=repository_adapter.session,
    )
    monkeypatch.setattr(repository_adapter.repository_class, 'max_limit', 5000)
    await repository_adapter.call(
        repo.saves,
        [PaginationLimitModel(value=i) for i in range(3)],
    )

    results = await repository_adapter.call(repo.find, limit=2000)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_default_max_limit_is_1000(repository_adapter):
    assert repository_adapter.repository_class.max_limit == 1000


@pytest.mark.asyncio
async def test_max_limit_can_be_disabled(repository_adapter, monkeypatch):
    repo = repository_adapter.repository_class(
        PaginationLimitModel,
        session=repository_adapter.session,
    )
    monkeypatch.setattr(repository_adapter.repository_class, 'max_limit', None)
    await repository_adapter.call(
        repo.saves,
        [PaginationLimitModel(value=i) for i in range(3)],
    )

    results = await repository_adapter.call(repo.find, limit=10_000_000)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_zero_limit_and_offset_are_allowed(repository_adapter, seeded_repo):
    results = await repository_adapter.call(seeded_repo.find, limit=0)
    assert results == []

    results = await repository_adapter.call(seeded_repo.find, offset=0, limit=5)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_omitted_limit_returns_all_rows_and_logs_warning(
    repository_adapter,
    seeded_repo,
):
    with pytest.warns(RuntimeWarning, match="without a limit"):
        results = await repository_adapter.call(seeded_repo.find)

    assert len(results) == 5


@pytest.mark.asyncio
async def test_omitted_limit_warning_points_to_caller(
    repository_adapter,
    seeded_repo,
):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if repository_adapter.mode == 'sync':
            seeded_repo.find(); expected_lineno = sys._getframe().f_lineno  # noqa: E702
        else:
            await seeded_repo.find(); expected_lineno = sys._getframe().f_lineno  # noqa: E702

    assert len(caught) == 1
    assert os.path.normcase(caught[0].filename) == os.path.normcase(__file__)
    assert caught[0].lineno == expected_lineno


@pytest.mark.asyncio
async def test_sqlite_negative_limit_does_not_reach_session_execute(
    repository_adapter,
    seeded_repo,
):
    with patch.object(
        seeded_repo.session,
        "execute",
        wraps=seeded_repo.session.execute,
    ) as mock_execute:
        with pytest.raises(ValueError):
            await repository_adapter.call(seeded_repo.find, limit=-1)

    mock_execute.assert_not_called()


pytestmark = pytest.mark.filterwarnings(
    r"ignore:find\(\) was called without a limit:RuntimeWarning"
)
