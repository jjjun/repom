from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
import pytest

from repom.models.base_model import BaseModel


class SaveRefreshModel(BaseModel, use_created_at=True, use_updated_at=True):
    __tablename__ = 'save_refresh_semantics'

    name: Mapped[str] = mapped_column(String(100), nullable=False)


def assert_timestamps_are_loaded(instance):
    assert isinstance(instance.created_at, datetime)
    assert instance.created_at.tzinfo == timezone.utc
    assert isinstance(instance.updated_at, datetime)
    assert instance.updated_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_external_session_save_requires_refresh(repository_adapter):
    repo = repository_adapter.repository_class(
        SaveRefreshModel,
        session=repository_adapter.session,
    )
    instance = SaveRefreshModel(name='external session')

    saved = await repository_adapter.call(repo.save, instance)

    assert saved.id is not None
    assert saved.created_at is None
    assert saved.updated_at is None

    await repository_adapter.call(repository_adapter.session.refresh, saved)
    assert_timestamps_are_loaded(saved)


@pytest.mark.asyncio
async def test_internal_session_save_refreshes_timestamps(repository_adapter):
    repo = repository_adapter.repository_class(SaveRefreshModel)

    saved = await repository_adapter.call(
        repo.save,
        SaveRefreshModel(name='internal session'),
    )

    assert saved.id is not None
    assert_timestamps_are_loaded(saved)


@pytest.mark.asyncio
async def test_internal_bulk_writes_refresh_timestamps(repository_adapter):
    repo = repository_adapter.repository_class(SaveRefreshModel)
    bulk_items = [
        SaveRefreshModel(name='internal bulk insert one'),
        SaveRefreshModel(name='internal bulk insert two'),
    ]
    saved_items = [SaveRefreshModel(name='internal saves')]

    returned_items = await repository_adapter.call(repo.bulk_insert, bulk_items)
    await repository_adapter.call(repo.saves, saved_items)

    assert returned_items == bulk_items
    for item in bulk_items + saved_items:
        assert_timestamps_are_loaded(item)


@pytest.mark.asyncio
async def test_external_session_update_preserves_created_at(repository_adapter):
    repo = repository_adapter.repository_class(
        SaveRefreshModel,
        session=repository_adapter.session,
    )
    saved = await repository_adapter.call(
        repo.save,
        SaveRefreshModel(name='before update'),
    )
    await repository_adapter.call(repository_adapter.session.refresh, saved)
    created_at = saved.created_at

    saved.name = 'after update'
    updated = await repository_adapter.call(repo.save, saved)
    await repository_adapter.call(repository_adapter.session.refresh, updated)

    assert updated.name == 'after update'
    assert updated.created_at == created_at
    assert_timestamps_are_loaded(updated)
