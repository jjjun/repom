"""Test fixture manager sessions share the test-owned transaction connection."""

from contextlib import asynccontextmanager, contextmanager

import pytest
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

import repom.database as database_module
from repom.database import Base, DatabaseManager
from repom.testing import create_async_test_fixtures, create_test_fixtures


class ConnectionBindingModel(Base):
    __tablename__ = "connection_binding_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False)


@contextmanager
def _sync_fixture_value(fixture, *args):
    generator = fixture.__wrapped__(*args)
    value = next(generator)
    try:
        yield value
    finally:
        try:
            next(generator)
        except StopIteration:
            pass
        else:
            raise AssertionError("fixture yielded more than once")


@asynccontextmanager
async def _async_fixture_value(fixture, *args):
    generator = fixture.__wrapped__(*args)
    value = await anext(generator)
    try:
        yield value
    finally:
        try:
            await anext(generator)
        except StopAsyncIteration:
            pass
        else:
            raise AssertionError("fixture yielded more than once")


@pytest.mark.parametrize("storage", ["memory", "file"])
def test_sync_manager_transaction_joins_and_rolls_back_with_fixture(
    storage, tmp_path, monkeypatch
):
    db_url = (
        "sqlite:///:memory:"
        if storage == "memory"
        else f"sqlite:///{(tmp_path / 'sync.sqlite3').as_posix()}"
    )
    manager = DatabaseManager()
    previous_engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(database_module, "_db_manager", manager)
    engine_fixture, db_test_fixture = create_test_fixtures(
        db_url=db_url,
        model_loader=lambda: None,
        allow_destructive=True,
        bind_global_manager=True,
    )

    try:
        with manager.bind_engine_for_tests(previous_engine):
            previous_factory = manager.get_sync_session_factory()
            with _sync_fixture_value(engine_fixture) as fixture_engine:
                assert database_module.get_db_manager() is manager
                assert "get_db_manager" in database_module.__all__
                assert database_module.get_sync_engine() is fixture_engine

                with _sync_fixture_value(db_test_fixture, fixture_engine) as db_test:
                    connection = db_test().connection()
                    transaction = connection.get_transaction()
                    assert transaction is not None

                    with contextmanager(database_module.get_db_transaction)() as session:
                        session.add(ConnectionBindingModel(value="written by manager"))

                    assert transaction.is_active
                    values = db_test.execute(select(ConnectionBindingModel.value)).scalars().all()
                    assert values == ["written by manager"]

                assert manager._sync_session_factory is None

                with _sync_fixture_value(db_test_fixture, fixture_engine) as next_db_test:
                    values = next_db_test.execute(
                        select(ConnectionBindingModel.value)
                    ).scalars().all()
                    assert values == []

            assert manager.get_sync_engine() is previous_engine
            assert manager.get_sync_session_factory() is previous_factory

            connection = previous_engine.connect()
            with pytest.raises(TypeError, match="engine must be"):
                with manager.bind_engine_for_tests(connection):
                    pass
            connection.close()
    finally:
        previous_engine.dispose()


@pytest.mark.parametrize("storage", ["memory", "file"])
@pytest.mark.asyncio
async def test_async_manager_transaction_joins_and_rolls_back_with_fixture(
    storage, tmp_path, monkeypatch
):
    db_url = (
        "sqlite:///:memory:"
        if storage == "memory"
        else f"sqlite:///{(tmp_path / 'async.sqlite3').as_posix()}"
    )
    manager = DatabaseManager()
    previous_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database_module, "_db_manager", manager)
    engine_fixture, db_test_fixture = create_async_test_fixtures(
        db_url=db_url,
        model_loader=lambda: None,
        allow_destructive=True,
        bind_global_manager=True,
    )

    try:
        with manager.bind_engine_for_tests(previous_engine):
            previous_factory = await manager.get_async_session_factory()
            async with _async_fixture_value(engine_fixture) as fixture_engine:
                assert database_module.get_db_manager() is manager
                assert await database_module.get_async_engine() is fixture_engine

                async with _async_fixture_value(
                    db_test_fixture, fixture_engine
                ) as async_db_test:
                    connection = await async_db_test.connection()
                    transaction = connection.get_transaction()
                    assert transaction is not None

                    async with asynccontextmanager(
                        database_module.get_async_db_transaction
                    )() as session:
                        session.add(
                            ConnectionBindingModel(value="written by async manager")
                        )

                    assert transaction.is_active
                    result = await async_db_test.execute(
                        select(ConnectionBindingModel.value)
                    )
                    assert result.scalars().all() == ["written by async manager"]

                assert manager._async_session_factory is None

                async with _async_fixture_value(
                    db_test_fixture, fixture_engine
                ) as next_async_db_test:
                    result = await next_async_db_test.execute(
                        select(ConnectionBindingModel.value)
                    )
                    assert result.scalars().all() == []

            assert await manager.get_async_engine() is previous_engine
            assert await manager.get_async_session_factory() is previous_factory
    finally:
        await previous_engine.dispose()
