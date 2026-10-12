import warnings

import pytest
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from repom.mixins import SoftDeletableMixin
from repom.models.base_model import BaseModel
from repom.repositories import AsyncBaseRepository, BaseRepository, FilterParams


class FindAllRecord(BaseModel, SoftDeletableMixin):
    __tablename__ = "find_all_records"

    category: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)


class CompositeFindAllRecord(BaseModel):
    __tablename__ = "composite_find_all_records"
    use_id = False

    partition: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)


class UuidFindAllRecord(BaseModel, use_uuid=True):
    __tablename__ = "uuid_find_all_records"

    value: Mapped[int] = mapped_column(Integer, nullable=False)


class FindAllParams(FilterParams):
    category: str | None = None


class FindAllRepository(BaseRepository[FindAllRecord]):
    field_to_column = {"category": FindAllRecord.category}


class AsyncFindAllRepository(AsyncBaseRepository[FindAllRecord]):
    field_to_column = {"category": FindAllRecord.category}


async def _collect_pages(repo, mode, **kwargs):
    if mode == "sync":
        return list(repo.iter_pages(**kwargs))
    return [page async for page in repo.iter_pages(**kwargs)]


def _find_all_repository(repository_adapter):
    repository_class = (
        FindAllRepository
        if repository_adapter.mode == "sync"
        else AsyncFindAllRepository
    )
    return repository_class(FindAllRecord, session=repository_adapter.session)


@pytest.mark.asyncio
async def test_find_all_matches_unbounded_find(repository_adapter):
    repo = _find_all_repository(repository_adapter)
    await repository_adapter.call(
        repo.saves,
        [FindAllRecord(category="all", value=value) for value in range(5)],
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        expected = await repository_adapter.call(repo.find)
    actual = await repository_adapter.call(repo.find_all, page_size=2)

    assert [record.id for record in actual] == [record.id for record in expected]


@pytest.mark.asyncio
async def test_iter_pages_yields_multiple_pages_without_runtime_warnings(
    repository_adapter,
):
    repo = _find_all_repository(repository_adapter)
    await repository_adapter.call(
        repo.saves,
        [FindAllRecord(category="all", value=value) for value in range(5)],
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pages = await _collect_pages(repo, repository_adapter.mode, page_size=2)

    assert [len(page) for page in pages] == [2, 2, 1]
    assert [record.value for page in pages for record in page] == list(range(5))
    assert caught == []


@pytest.mark.asyncio
async def test_find_all_combines_params_and_filters(repository_adapter):
    repo = _find_all_repository(repository_adapter)
    await repository_adapter.call(
        repo.saves,
        [
            FindAllRecord(category="wanted", value=1),
            FindAllRecord(category="wanted", value=2),
            FindAllRecord(category="wanted", value=3),
            FindAllRecord(category="other", value=3),
        ],
    )

    records = await repository_adapter.call(
        repo.find_all,
        filters=[FindAllRecord.value >= 2],
        params=FindAllParams(category="wanted"),
        page_size=1,
    )

    assert [record.value for record in records] == [2, 3]


@pytest.mark.asyncio
async def test_find_all_excludes_soft_deleted_records_by_default(repository_adapter):
    repo = _find_all_repository(repository_adapter)
    records = [
        FindAllRecord(category="all", value=1),
        FindAllRecord(category="all", value=2),
    ]
    await repository_adapter.call(repo.saves, records)
    await repository_adapter.call(repo.soft_delete, records[1].id)

    active_records = await repository_adapter.call(repo.find_all, page_size=1)
    all_records = await repository_adapter.call(
        repo.find_all,
        include_deleted=True,
        page_size=1,
    )

    assert [record.value for record in active_records] == [1]
    assert [record.value for record in all_records] == [1, 2]


@pytest.mark.asyncio
async def test_iter_pages_rejects_composite_primary_keys(repository_adapter):
    repo = repository_adapter.repository_class(
        CompositeFindAllRecord,
        session=repository_adapter.session,
    )

    with pytest.raises(ValueError, match="single-column primary key"):
        await _collect_pages(repo, repository_adapter.mode)


@pytest.mark.asyncio
async def test_iter_pages_supports_string_uuid_primary_keys(repository_adapter):
    repo = repository_adapter.repository_class(
        UuidFindAllRecord,
        session=repository_adapter.session,
    )
    records = [UuidFindAllRecord(value=value) for value in range(5)]
    await repository_adapter.call(repo.saves, records)

    pages = await _collect_pages(repo, repository_adapter.mode, page_size=2)
    results = [record for page in pages for record in page]

    assert all(isinstance(record.id, str) for record in results)
    assert [record.id for record in results] == sorted(record.id for record in records)


@pytest.mark.asyncio
async def test_iter_pages_rejects_page_size_above_max_limit(repository_adapter):
    repo = _find_all_repository(repository_adapter)
    repo.max_limit = 2

    with pytest.raises(ValueError, match="limit must not exceed max_limit"):
        await _collect_pages(repo, repository_adapter.mode, page_size=3)


@pytest.mark.asyncio
async def test_iter_pages_rejects_zero_page_size(repository_adapter):
    repo = _find_all_repository(repository_adapter)

    with pytest.raises(ValueError, match="page_size must be greater than zero"):
        await _collect_pages(repo, repository_adapter.mode, page_size=0)
