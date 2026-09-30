"""
FilterParams 経由の文字列フィルタが LIKE のワイルドカードを誤って解釈しないこと、
および ListJSON の要素一致が部分文字列ではなく完全一致であることを確認するテスト
（repom#127）。

_value_to_filter() はかつて autoescape なしの contains() を既定で使っており、
"%" 一文字で全件がヒットしたり、交互ワイルドカードパターンでバックトラッキング
DoS を起こせる欠陥があった。field_to_column の既定値も完全一致（==）に変更し、
部分一致・前方一致は contains_column() / prefix_column() で明示する。
"""
from datetime import date
from typing import Optional

import pytest

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel
from repom import AsyncBaseRepository, BaseRepository, FilterParams
from repom.repositories import (
    contains_column,
    gte_column,
    gt_column,
    lte_column,
    lt_column,
    prefix_column,
)


class FilterMatchModel(BaseModel):
    __tablename__ = 'filter_match_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class FilterMatchParams(FilterParams):
    name: Optional[str] = None


class ExactFilterRepository(BaseRepository[FilterMatchModel]):
    field_to_column = {"name": FilterMatchModel.name}

    def __init__(self, session):
        super().__init__(FilterMatchModel, session)


class ContainsFilterRepository(BaseRepository[FilterMatchModel]):
    field_to_column = {"name": contains_column(FilterMatchModel.name)}

    def __init__(self, session):
        super().__init__(FilterMatchModel, session)


class PrefixFilterRepository(BaseRepository[FilterMatchModel]):
    field_to_column = {"name": prefix_column(FilterMatchModel.name)}

    def __init__(self, session):
        super().__init__(FilterMatchModel, session)


class FilterRangeModel(BaseModel):
    __tablename__ = 'filter_range_model'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer)
    created_on: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(400))


class FilterRangeParams(FilterParams):
    number_gte: Optional[int] = None
    number_gt: Optional[int] = None
    number_lte: Optional[int] = None
    number_lt: Optional[int] = None
    created_on_gte: Optional[date] = None
    created_on_lt: Optional[date] = None
    name_gte: Optional[str] = None


class FilterRangeRepository(BaseRepository[FilterRangeModel]):
    field_to_column = {
        "number_gte": gte_column(FilterRangeModel.number),
        "number_gt": gt_column(FilterRangeModel.number),
        "number_lte": lte_column(FilterRangeModel.number),
        "number_lt": lt_column(FilterRangeModel.number),
        "created_on_gte": gte_column(FilterRangeModel.created_on),
        "created_on_lt": lt_column(FilterRangeModel.created_on),
        "name_gte": gte_column(FilterRangeModel.name),
    }

    def __init__(self, session):
        super().__init__(FilterRangeModel, session)


class AsyncFilterRangeRepository(AsyncBaseRepository[FilterRangeModel]):
    field_to_column = FilterRangeRepository.field_to_column

    def __init__(self, session):
        super().__init__(FilterRangeModel, session)


def test_field_to_column_defaults_to_exact_match(db_test):
    """素のカラムを渡した場合、文字列フィールドは部分一致ではなく完全一致になる"""
    repo = ExactFilterRepository(session=db_test)
    repo.saves([
        FilterMatchModel(name="alpha"),
        FilterMatchModel(name="alphabet"),
    ])

    results = repo.find(params=FilterMatchParams(name="alpha"))

    assert {item.name for item in results} == {"alpha"}


def test_exact_match_does_not_treat_percent_as_wildcard(db_test):
    """既定の完全一致では "%" はワイルドカードではなくリテラルとして扱われる"""
    repo = ExactFilterRepository(session=db_test)
    repo.saves([
        FilterMatchModel(name="100%"),
        FilterMatchModel(name="other"),
    ])

    results = repo.find(params=FilterMatchParams(name="%"))

    assert results == []


def test_contains_column_escapes_percent(db_test):
    """contains_column() は "%" をエスケープし、リテラルとしてのみ一致させる"""
    repo = ContainsFilterRepository(session=db_test)
    repo.saves([
        FilterMatchModel(name="100%"),
        FilterMatchModel(name="other"),
    ])

    results = repo.find(params=FilterMatchParams(name="100%"))

    assert {item.name for item in results} == {"100%"}


def test_contains_column_escapes_underscore(db_test):
    """contains_column() は "_" をエスケープし、任意の1文字ではなくリテラルとして扱う"""
    repo = ContainsFilterRepository(session=db_test)
    repo.saves([
        FilterMatchModel(name="a_b"),
        FilterMatchModel(name="axb"),
    ])

    results = repo.find(params=FilterMatchParams(name="a_b"))

    assert {item.name for item in results} == {"a_b"}


def test_prefix_column_matches_prefix_only(db_test):
    """prefix_column() は前方一致のみで、末尾や途中に含まれる場合はヒットしない"""
    repo = PrefixFilterRepository(session=db_test)
    repo.saves([
        FilterMatchModel(name="alpha"),
        FilterMatchModel(name="beta_alpha"),
    ])

    results = repo.find(params=FilterMatchParams(name="alpha"))

    assert {item.name for item in results} == {"alpha"}


def test_range_match_modes_handle_integer_and_date_fields(db_test):
    repo = FilterRangeRepository(session=db_test)
    repo.bulk_insert([
        FilterRangeModel(number=1, created_on=date(2025, 1, 1), name="one"),
        FilterRangeModel(number=2, created_on=date(2025, 1, 2), name="two"),
        FilterRangeModel(number=3, created_on=date(2025, 1, 3), name="three"),
    ])

    assert [item.number for item in repo.find(params=FilterRangeParams(number_gte=2), limit=10)] == [2, 3]
    assert [item.number for item in repo.find(params=FilterRangeParams(number_gt=2), limit=10)] == [3]
    assert [item.number for item in repo.find(params=FilterRangeParams(number_lte=2), limit=10)] == [1, 2]
    assert [item.number for item in repo.find(params=FilterRangeParams(number_lt=2), limit=10)] == [1]
    assert [item.number for item in repo.find(
        params=FilterRangeParams(created_on_gte=date(2025, 1, 2), created_on_lt=date(2025, 1, 3)),
        limit=10,
    )] == [2]


def test_range_match_modes_do_not_apply_like_string_length_limit(db_test):
    repo = FilterRangeRepository(session=db_test)
    long_name = "a" * 300
    repo.save(FilterRangeModel(number=1, created_on=date(2025, 1, 1), name=long_name))

    results = repo.find(params=FilterRangeParams(name_gte=long_name), limit=10)

    assert [item.name for item in results] == [long_name]


@pytest.mark.asyncio
async def test_async_range_match_modes_handle_integer_and_date_fields(async_db_test):
    repo = AsyncFilterRangeRepository(session=async_db_test)
    await repo.bulk_insert([
        FilterRangeModel(number=1, created_on=date(2025, 1, 1), name="one"),
        FilterRangeModel(number=2, created_on=date(2025, 1, 2), name="two"),
        FilterRangeModel(number=3, created_on=date(2025, 1, 3), name="three"),
    ])

    assert [item.number for item in await repo.find(params=FilterRangeParams(number_gte=2), limit=10)] == [2, 3]
    assert [item.number for item in await repo.find(params=FilterRangeParams(number_gt=2), limit=10)] == [3]
    assert [item.number for item in await repo.find(params=FilterRangeParams(number_lte=2), limit=10)] == [1, 2]
    assert [item.number for item in await repo.find(params=FilterRangeParams(number_lt=2), limit=10)] == [1]
    assert [item.number for item in await repo.find(
        params=FilterRangeParams(created_on_gte=date(2025, 1, 2), created_on_lt=date(2025, 1, 3)),
        limit=10,
    )] == [2]


@pytest.mark.asyncio
async def test_async_range_match_modes_do_not_apply_like_string_length_limit(async_db_test):
    repo = AsyncFilterRangeRepository(session=async_db_test)
    long_name = "a" * 300
    await repo.save(FilterRangeModel(number=1, created_on=date(2025, 1, 1), name=long_name))

    results = await repo.find(params=FilterRangeParams(name_gte=long_name), limit=10)

    assert [item.name for item in results] == [long_name]


def test_contains_filter_rejects_value_over_max_length(db_test):
    """交互ワイルドカードパターンによるバックトラッキング DoS を防ぐため、
    LIKE に渡す前に長さ上限で拒否する"""
    long_value = "%a" * 200
    repo = ContainsFilterRepository(session=db_test)

    with pytest.raises(ValueError, match="exceeds the maximum length"):
        repo.find(params=FilterMatchParams(name=long_value))


@pytest.mark.asyncio
async def test_instance_field_mapping_overrides_class_mapping(repository_adapter):
    class ClassMappedRepository(repository_adapter.repository_class):
        field_to_column = {"name": FilterMatchModel.id}

    repo = ClassMappedRepository(
        FilterMatchModel,
        session=repository_adapter.session,
    )
    repo.field_to_column = {"name": FilterMatchModel.name}

    filters = repo._build_filters(FilterMatchParams(name="alpha"))

    assert filters[0].left.key == "name"
    assert ClassMappedRepository.field_to_column["name"].key == "id"

pytestmark = pytest.mark.filterwarnings(
    r"ignore:find\(\) was called without a limit:RuntimeWarning"
)
