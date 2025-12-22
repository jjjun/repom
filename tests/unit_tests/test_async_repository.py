"""
AsyncBaseRepository の非同期版テスト

test_repository.py の全テストケースを非同期版に変換したもの。
"""
from tests._init import *
from sqlalchemy import Integer, inspect, select, desc, and_
from sqlalchemy.orm import Mapped, mapped_column
import pytest
from datetime import datetime
from repom.base_model import BaseModel
from repom.async_base_repository import AsyncBaseRepository


class AsyncSimpleModel(BaseModel):
    __tablename__ = 'async_simple_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class AsyncSimpleRepository(AsyncBaseRepository[AsyncSimpleModel]):
    def __init__(self, session):
        super().__init__(AsyncSimpleModel, session)


@pytest.mark.asyncio
async def test_create(async_db_test):
    """
    AsyncSimpleModelの基本的な作成テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    obj = AsyncSimpleModel(value=123)
    saved_obj = await repo.save(obj)
    assert saved_obj is obj
    assert obj.id is not None


@pytest.mark.asyncio
async def test_get_by_id(async_db_test):
    """
    AsyncSimpleModelのIDによる取得テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    obj = AsyncSimpleModel(value=456)
    await repo.save(obj)
    retrieved = await repo.get_by_id(obj.id)
    assert retrieved is not None
    assert retrieved.id == obj.id


@pytest.mark.asyncio
async def test_get_by_column_returns_all_matches(async_db_test):
    repo = AsyncSimpleRepository(session=async_db_test)
    obj = AsyncSimpleModel(value=789)
    await repo.save(obj)

    retrieved = await repo.get_by("value", 789)

    assert isinstance(retrieved, list)
    assert len(retrieved) == 1
    assert retrieved[0].id == obj.id


@pytest.mark.asyncio
async def test_get_by_with_additional_filters_single(async_db_test):
    repo = AsyncSimpleRepository(session=async_db_test)
    first = await repo.save(AsyncSimpleModel(value=1))
    await repo.save(AsyncSimpleModel(value=1))

    retrieved = await repo.get_by("value", 1, AsyncSimpleModel.id == first.id, single=True)

    assert retrieved == first


@pytest.mark.asyncio
async def test_get_by_returns_multiple_matches(async_db_test):
    repo = AsyncSimpleRepository(session=async_db_test)
    first = await repo.save(AsyncSimpleModel(value=5))
    second = await repo.save(AsyncSimpleModel(value=5))

    retrieved = await repo.get_by("value", 5)

    assert isinstance(retrieved, list)
    assert {item.id for item in retrieved} == {first.id, second.id}


@pytest.mark.asyncio
async def test_get_by_invalid_column(async_db_test):
    repo = AsyncSimpleRepository(session=async_db_test)
    await repo.save(AsyncSimpleModel(value=123))

    with pytest.raises(AttributeError):
        await repo.get_by("unknown", 123)


@pytest.mark.asyncio
async def test_get_all(async_db_test):
    """
    AsyncSimpleModelの全取得テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    obj1 = AsyncSimpleModel(value=1)
    obj2 = AsyncSimpleModel(value=2)
    await repo.save(obj1)
    await repo.save(obj2)
    all_objs = await repo.get_all()
    assert len(all_objs) >= 2


@pytest.mark.asyncio
async def test_remove(async_db_test):
    """
    AsyncSimpleModelの削除テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    obj = AsyncSimpleModel(value=10)
    await repo.save(obj)
    await repo.remove(obj)
    assert await repo.get_by_id(obj.id) is None


@pytest.mark.asyncio
async def test_dict_save(async_db_test):
    """
    dict型のデータをモデルインスタンスにして保存するテスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    data = {"value": 99}
    saved_instance = await repo.dict_save(data)
    assert saved_instance.id is not None
    assert saved_instance.value == 99
    assert await repo.get_by_id(saved_instance.id) == saved_instance


@pytest.mark.asyncio
async def test_saves(async_db_test):
    """
    Listの中に入ったインスタンスを保存するテスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    objs = [AsyncSimpleModel(value=1), AsyncSimpleModel(value=2)]
    await repo.saves(objs)
    all_objs = await repo.get_all()
    assert len(all_objs) >= 2


@pytest.mark.asyncio
async def test_dict_saves(async_db_test):
    """
    Listの中に入ったdict型のデータをモデルインスタンスにして保存するテスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    data_list = [{"value": 1}, {"value": 2}]
    await repo.dict_saves(data_list)
    all_objs = await repo.get_all()
    assert len(all_objs) >= 2
    assert all_objs[0].value == 1
    assert all_objs[1].value == 2


@pytest.mark.asyncio
async def test_find_with_offset(async_db_test):
    """
    offsetによる取得テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    objs = [AsyncSimpleModel(value=i) for i in range(5)]
    await repo.saves(objs)
    offset_objs = await repo.find(offset=2)
    assert len(offset_objs) == 3
    assert offset_objs[0].value == 2


@pytest.mark.asyncio
async def test_find_with_limit(async_db_test):
    """
    limitによる取得テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    objs = [AsyncSimpleModel(value=i) for i in range(5)]
    await repo.saves(objs)
    limited_objs = await repo.find(limit=2)
    assert len(limited_objs) == 2
    assert limited_objs[0].value == 0


@pytest.mark.asyncio
async def test_find_with_order_by(async_db_test):
    """
    order_byによる取得テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    objs = [AsyncSimpleModel(value=i) for i in range(5)]
    await repo.saves(objs)
    ordered_objs = await repo.find(order_by=desc(AsyncSimpleModel.id))
    assert len(ordered_objs) == 5
    assert ordered_objs[0].value == 4
    assert ordered_objs[-1].value == 0


@pytest.mark.asyncio
async def test_find_with_order_by_default(async_db_test):
    """
    order_byのデフォルト値がidの昇順であることを確認するテスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    objs = [AsyncSimpleModel(value=i) for i in range(5)]
    await repo.saves(objs)
    ordered_objs = await repo.find()
    assert len(ordered_objs) == 5
    assert ordered_objs[0].value == 0
    assert ordered_objs[-1].value == 4


@pytest.mark.asyncio
async def test_find_without_limit(async_db_test):
    """
    limitを指定しない場合の取得テスト(全て取得する)
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    objs = [AsyncSimpleModel(value=i) for i in range(40)]
    await repo.saves(objs)
    all_objs = await repo.find()
    assert len(all_objs) == 40
    assert all_objs[0].value == 0
    assert all_objs[-1].value == 39


@pytest.mark.asyncio
async def test_count(async_db_test):
    """
    AsyncBaseRepository.countの基本動作テスト
    """
    repo = AsyncSimpleRepository(session=async_db_test)
    # 3件追加
    objs = [AsyncSimpleModel(value=i) for i in range(3)]
    await repo.saves(objs)
    # 全件カウント
    assert await repo.count() == 3
    # value=1 のみカウント
    from sqlalchemy import and_
    filters = [AsyncSimpleModel.value == 1]
    assert await repo.count(filters) == 1
    # 存在しない値
    filters = [AsyncSimpleModel.value == 999]
    assert await repo.count(filters) == 0
