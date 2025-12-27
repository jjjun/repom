from tests._init import *
from sqlalchemy import Integer, String, inspect, select, desc, and_
from sqlalchemy.orm import Mapped, mapped_column
import pytest
from datetime import datetime
from typing import Optional
from repom.base_model import BaseModel
from repom.base_repository import BaseRepository
from repom.base_model_auto import BaseModelAuto
from repom.mixins import SoftDeletableMixin
from repom.repositories import FilterParams


class SimpleModel(BaseModel):
    __tablename__ = 'simple_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class SimpleRepository(BaseRepository[SimpleModel]):
    def __init__(self, session):
        super().__init__(SimpleModel, session)


class SimpleFilterParams(FilterParams):
    value: Optional[int] = None
    other: Optional[int] = None


class FilterableRepository(SimpleRepository):
    def _build_filters(self, params: Optional[FilterParams]) -> list:
        filters = super()._build_filters(params)
        if params is None:
            return filters

        if params.value is not None:
            filters.append(SimpleModel.value == params.value)
        return filters


class SoftDeleteCountModel(BaseModelAuto, SoftDeletableMixin):
    """count の include_deleted フラグ検証用モデル"""

    __tablename__ = 'soft_delete_count_items'

    name: Mapped[str] = mapped_column(String(100), nullable=False)


def test_create(db_test):
    """
    SimpleModelの基本的な作成テスト
    """
    repo = SimpleRepository(session=db_test)
    obj = SimpleModel(value=123)
    saved_obj = repo.save(obj)
    assert saved_obj is obj
    assert obj.id is not None


def test_get_by_id(db_test):
    """
    SimpleModelのIDによる取得テスト
    """
    repo = SimpleRepository(session=db_test)
    obj = SimpleModel(value=456)
    repo.save(obj)
    retrieved = repo.get_by_id(obj.id)
    assert retrieved is not None
    assert retrieved.id == obj.id


def test_get_by_column_returns_all_matches(db_test):
    repo = SimpleRepository(session=db_test)
    obj = SimpleModel(value=789)
    repo.save(obj)

    retrieved = repo.get_by("value", 789)

    assert isinstance(retrieved, list)
    assert len(retrieved) == 1
    assert retrieved[0].id == obj.id


def test_get_by_with_additional_filters_single(db_test):
    repo = SimpleRepository(session=db_test)
    first = repo.save(SimpleModel(value=1))
    repo.save(SimpleModel(value=1))

    retrieved = repo.get_by("value", 1, SimpleModel.id == first.id, single=True)

    assert retrieved == first


def test_get_by_returns_multiple_matches(db_test):
    repo = SimpleRepository(session=db_test)
    first = repo.save(SimpleModel(value=5))
    second = repo.save(SimpleModel(value=5))

    retrieved = repo.get_by("value", 5)

    assert isinstance(retrieved, list)
    assert {item.id for item in retrieved} == {first.id, second.id}


def test_get_by_invalid_column(db_test):
    repo = SimpleRepository(session=db_test)
    repo.save(SimpleModel(value=123))

    with pytest.raises(AttributeError):
        repo.get_by("unknown", 123)


def test_get_all(db_test):
    """
    SimpleModelの全取得テスト
    """
    repo = SimpleRepository(session=db_test)
    obj1 = SimpleModel(value=1)
    obj2 = SimpleModel(value=2)
    repo.save(obj1)
    repo.save(obj2)
    all_objs = repo.get_all()
    assert len(all_objs) >= 2


def test_remove(db_test):
    """
    SimpleModelの削除テスト
    """
    repo = SimpleRepository(session=db_test)
    obj = SimpleModel(value=10)
    repo.save(obj)
    repo.remove(obj)
    assert repo.get_by_id(obj.id) is None


def test_dict_save(db_test):
    """
    dict型のデータをモデルインスタンスにして保存するテスト
    """
    repo = SimpleRepository(session=db_test)
    data = {"value": 99}
    saved_instance = repo.dict_save(data)
    assert saved_instance.id is not None
    assert saved_instance.value == 99
    assert repo.get_by_id(saved_instance.id) == saved_instance


def test_saves(db_test):
    """
    Listの中に入ったインスタンスを保存するテスト
    """
    repo = SimpleRepository(session=db_test)
    objs = [SimpleModel(value=1), SimpleModel(value=2)]
    repo.saves(objs)
    all_objs = repo.get_all()
    assert len(all_objs) >= 2


def test_dict_saves(db_test):
    """
    Listの中に入ったdict型のデータをモデルインスタンスにして保存するテスト
    """
    repo = SimpleRepository(session=db_test)
    data_list = [{"value": 1}, {"value": 2}]
    repo.dict_saves(data_list)
    all_objs = repo.get_all()
    assert len(all_objs) >= 2
    assert all_objs[0].value == 1
    assert all_objs[1].value == 2


def test_find_with_offset(db_test):
    """
    offsetによる取得テスト
    """
    repo = SimpleRepository(session=db_test)
    objs = [SimpleModel(value=i) for i in range(5)]
    repo.saves(objs)
    offset_objs = repo.find(offset=2)
    assert len(offset_objs) == 3
    assert offset_objs[0].value == 2


def test_find_with_limit(db_test):
    """
    limitによる取得テスト
    """
    repo = SimpleRepository(session=db_test)
    objs = [SimpleModel(value=i) for i in range(5)]
    repo.saves(objs)
    limited_objs = repo.find(limit=2)
    assert len(limited_objs) == 2
    assert limited_objs[0].value == 0


def test_find_with_order_by(db_test):
    """
    order_byによる取得テスト
    """
    repo = SimpleRepository(session=db_test)
    objs = [SimpleModel(value=i) for i in range(5)]
    repo.saves(objs)
    ordered_objs = repo.find(order_by=desc(SimpleModel.id))
    assert len(ordered_objs) == 5
    assert ordered_objs[0].value == 4
    assert ordered_objs[-1].value == 0


def test_find_with_order_by_default(db_test):
    """
    order_byのデフォルト値がidの昇順であることを確認するテスト
    """
    repo = SimpleRepository(session=db_test)
    objs = [SimpleModel(value=i) for i in range(5)]
    repo.saves(objs)
    ordered_objs = repo.find()
    assert len(ordered_objs) == 5
    assert ordered_objs[0].value == 0
    assert ordered_objs[-1].value == 4


def test_find_without_limit(db_test):
    """
    limitを指定しない場合の取得テスト(全て取得する)
    """
    repo = SimpleRepository(session=db_test)
    objs = [SimpleModel(value=i) for i in range(40)]
    repo.saves(objs)
    all_objs = repo.find()
    assert len(all_objs) == 40
    assert all_objs[0].value == 0
    assert all_objs[-1].value == 39


def test_build_filters_default_empty_when_params_absent_or_empty(db_test):
    repo = SimpleRepository(session=db_test)

    assert repo._build_filters(None) == []
    assert repo._build_filters(SimpleFilterParams()) == []


def test_find_uses_params_when_filters_not_provided(db_test):
    repo = FilterableRepository(session=db_test)
    repo.saves([SimpleModel(value=1), SimpleModel(value=2)])

    results = repo.find(params=SimpleFilterParams(value=1))

    assert {item.value for item in results} == {1}


def test_find_prefers_explicit_filters_over_params(db_test):
    repo = FilterableRepository(session=db_test)
    repo.saves([SimpleModel(value=1), SimpleModel(value=2)])

    results = repo.find(params=SimpleFilterParams(value=1), filters=[SimpleModel.value == 2])

    assert {item.value for item in results} == {2}


def test_count(db_test):
    """
    BaseRepository.countの基本動作テスト
    """
    repo = SimpleRepository(session=db_test)
    # 3件追加
    objs = [SimpleModel(value=i) for i in range(3)]
    repo.saves(objs)
    # 全件カウント
    assert repo.count() == 3
    # value=1 のみカウント
    from sqlalchemy import and_
    filters = [SimpleModel.value == 1]
    assert repo.count(filters) == 1
    # 存在しない値
    filters = [SimpleModel.value == 999]
    assert repo.count(filters) == 0


def test_count_respects_soft_delete_flag_on_soft_deletable_model(db_test):
    """count() はデフォルトで削除済みを除外し、フラグで含められる"""
    repo = BaseRepository(SoftDeleteCountModel, db_test)

    active = SoftDeleteCountModel(name="active")
    deleted = SoftDeleteCountModel(name="deleted")
    db_test.add_all([active, deleted])
    db_test.commit()

    deleted.soft_delete()
    db_test.commit()

    assert repo.count() == 1
    assert repo.count(include_deleted=True) == 2


def test_count_on_non_soft_deletable_model_accepts_flag(db_test):
    """非ソフトデリートモデルでも include_deleted が指定できる（挙動は変わらない）"""
    repo = SimpleRepository(session=db_test)
    repo.saves([SimpleModel(value=i) for i in range(2)])

    assert repo.count() == 2
    assert repo.count(include_deleted=True) == 2


def test_default_session_fallback():
    """
    セッション未指定時に get_db_session() を使用して動作することを確認
    """
    repo = BaseRepository(SimpleModel)
    created = repo.save(SimpleModel(value=111))

    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.value == 111

    repo.remove(fetched)
    assert repo.get_by_id(created.id) is None
