"""Default ordering shared by the sync and async repositories."""
from sqlalchemy import Integer, String, desc
from sqlalchemy.orm import Mapped, mapped_column
import pytest
import pytest_asyncio

from repom.models.base_model import BaseModel
from repom.repositories import AsyncBaseRepository, BaseRepository


class OrderTestModel(BaseModel):
    __tablename__ = 'order_test_items'

    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)


class SyncOrderTestRepository(BaseRepository[OrderTestModel]):
    allowed_order_columns = ['id', 'name', 'priority', 'created_at', 'updated_at']
    default_order_by = 'id:desc'


class AsyncOrderTestRepository(AsyncBaseRepository[OrderTestModel]):
    allowed_order_columns = ['id', 'name', 'priority', 'created_at', 'updated_at']
    default_order_by = 'id:desc'


@pytest_asyncio.fixture
async def ordered_repo(repository_adapter):
    repository_class = (
        SyncOrderTestRepository
        if repository_adapter.mode == 'sync'
        else AsyncOrderTestRepository
    )
    repo = repository_class(session=repository_adapter.session)
    items = [
        OrderTestModel(name='First', priority=1),
        OrderTestModel(name='Second', priority=2),
        OrderTestModel(name='Third', priority=3),
    ]
    await repository_adapter.call(repo.saves, items)
    return repo, items


@pytest.mark.asyncio
@pytest.mark.parametrize('order_by', ['omitted', None, ''])
async def test_find_uses_default_order(repository_adapter, ordered_repo, order_by):
    repo, items = ordered_repo
    kwargs = {} if order_by == 'omitted' else {'order_by': order_by}

    results = await repository_adapter.call(repo.find, limit=10, **kwargs)

    assert [item.id for item in results] == [item.id for item in reversed(items)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('order_by', 'expected_priorities'),
    [('id:asc', [1, 2, 3]), ('priority:asc', [1, 2, 3])],
)
async def test_explicit_order_overrides_default(
    repository_adapter,
    ordered_repo,
    order_by,
    expected_priorities,
):
    repo, _ = ordered_repo

    results = await repository_adapter.call(repo.find, order_by=order_by, limit=10)

    assert [item.priority for item in results] == expected_priorities


@pytest.mark.asyncio
@pytest.mark.parametrize('order_by', ['omitted', None])
async def test_repository_without_default_order_uses_ascending_id(
    repository_adapter,
    ordered_repo,
    order_by,
):
    _, items = ordered_repo
    repo = repository_adapter.repository_class(
        OrderTestModel,
        session=repository_adapter.session,
    )
    repo.allowed_order_columns = ['id', 'name', 'priority', 'created_at', 'updated_at']

    kwargs = {} if order_by == 'omitted' else {'order_by': order_by}
    results = await repository_adapter.call(repo.find, limit=10, **kwargs)

    assert [item.id for item in results] == [item.id for item in items]


@pytest.mark.asyncio
async def test_invalid_default_order_column_raises(repository_adapter):
    repo = repository_adapter.repository_class(
        OrderTestModel,
        session=repository_adapter.session,
    )
    repo.default_order_by = 'invalid_column:desc'

    with pytest.raises(ValueError, match='not allowed for sorting'):
        await repository_adapter.call(repo.find, limit=10)


@pytest.mark.asyncio
async def test_default_order_by_accepts_sqlalchemy_expression(
    repository_adapter,
    ordered_repo,
):
    _, _ = ordered_repo
    repo = repository_adapter.repository_class(
        OrderTestModel,
        session=repository_adapter.session,
    )
    repo.default_order_by = desc(OrderTestModel.priority)

    results = await repository_adapter.call(repo.find, limit=10)

    assert [item.priority for item in results] == [3, 2, 1]


@pytest.mark.asyncio
async def test_instance_order_and_limit_defaults_override_class_defaults(
    repository_adapter,
    ordered_repo,
):
    class RepositoryWithDefaults(repository_adapter.repository_class):
        allowed_order_columns = [
            'id', 'name', 'priority', 'created_at', 'updated_at'
        ]
        default_order_by = 'id:desc'
        max_limit = 3

    repo = RepositoryWithDefaults(
        OrderTestModel,
        session=repository_adapter.session,
    )
    repo.default_order_by = 'priority:asc'
    repo.max_limit = 1

    assert RepositoryWithDefaults.default_order_by == 'id:desc'
    assert RepositoryWithDefaults.max_limit == 3

    with pytest.raises(ValueError, match=r'limit must not exceed max_limit \(1\)'):
        await repository_adapter.call(repo.find, limit=2)

    results = await repository_adapter.call(repo.find, limit=1)
    assert [item.priority for item in results] == [1]


pytestmark = pytest.mark.filterwarnings(
    r"ignore:find\(\) was called without a limit:RuntimeWarning"
)
