"""
FilterParams 経由の文字列フィルタが LIKE のワイルドカードを誤って解釈しないこと、
および ListJSON の要素一致が部分文字列ではなく完全一致であることを確認するテスト
（repom#127）。

_value_to_filter() はかつて autoescape なしの contains() を既定で使っており、
"%" 一文字で全件がヒットしたり、交互ワイルドカードパターンでバックトラッキング
DoS を起こせる欠陥があった。field_to_column の既定値も完全一致（==）に変更し、
部分一致・前方一致は contains_column() / prefix_column() で明示する。
"""
import pytest
from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model import BaseModel
from repom import BaseRepository, FilterParams
from repom.repositories import contains_column, prefix_column


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
