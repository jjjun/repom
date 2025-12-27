from tests._init import *
from typing import List, Optional

from sqlalchemy import Integer, String, desc, inspect
from sqlalchemy.orm import Mapped, mapped_column, load_only

from repom.base_model import BaseModel
from repom import BaseRepository
from repom.repositories import FilterParams


class QueryBuilderItem(BaseModel):
    __tablename__ = 'query_builder_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rank: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(50))


class QueryBuilderParams(FilterParams):
    rank: Optional[int] = None
    categories: Optional[List[str]] = None
    name: Optional[str] = None


class TrackingRepository(BaseRepository[QueryBuilderItem]):
    field_to_column = {
        "rank": QueryBuilderItem.rank,
        "categories": QueryBuilderItem.category,
        "name": QueryBuilderItem.name,
    }

    def __init__(self, session):
        super().__init__(QueryBuilderItem, session)
        self.filters_built = False

    def _build_filters(self, params: Optional[FilterParams]) -> list:
        self.filters_built = True
        return super()._build_filters(params)


class DefaultOptionsRepository(TrackingRepository):
    default_options = [load_only(QueryBuilderItem.id, QueryBuilderItem.name)]


class DefaultOrderRepository(TrackingRepository):
    default_order_by = desc(QueryBuilderItem.rank)


def test_find_uses_filters_without_building_params(db_test):
    repo = TrackingRepository(db_test)
    repo.saves([
        QueryBuilderItem(rank=1, category='primary', name='alpha'),
        QueryBuilderItem(rank=2, category='secondary', name='beta'),
    ])

    results = repo.find(filters=[QueryBuilderItem.rank == 2])

    assert repo.filters_built is False
    assert [item.rank for item in results] == [2]


def test_find_builds_filters_from_params_when_filters_absent(db_test):
    repo = TrackingRepository(db_test)
    repo.saves([
        QueryBuilderItem(rank=1, category='primary', name='alpha'),
        QueryBuilderItem(rank=2, category='secondary', name='beta'),
    ])

    results = repo.find(params=QueryBuilderParams(rank=1))

    assert repo.filters_built is True
    assert [item.rank for item in results] == [1]


def test_default_options_class_attribute_applied_when_options_missing(db_test):
    repo = DefaultOptionsRepository(db_test)
    repo.saves([
        QueryBuilderItem(rank=1, category='primary', name='alpha'),
    ])

    result = repo.find()[0]
    state = inspect(result)

    assert 'category' in state.unloaded
    assert 'rank' in state.unloaded
    assert result.name == 'alpha'


def test_default_order_by_class_attribute_applied_when_order_missing(db_test):
    repo = DefaultOrderRepository(db_test)
    repo.saves([
        QueryBuilderItem(rank=1, category='primary', name='alpha'),
        QueryBuilderItem(rank=3, category='primary', name='gamma'),
        QueryBuilderItem(rank=2, category='secondary', name='beta'),
    ])

    results = repo.find()

    assert [item.rank for item in results] == [3, 2, 1]


def test_filter_params_mapping_supports_eq_in_contains(db_test):
    repo = TrackingRepository(db_test)
    repo.saves([
        QueryBuilderItem(rank=1, category='primary', name='alpha'),
        QueryBuilderItem(rank=2, category='secondary', name='beta'),
        QueryBuilderItem(rank=3, category='primary', name='charlie'),
    ])

    eq_results = repo.find(params=QueryBuilderParams(rank=2))
    in_results = repo.find(params=QueryBuilderParams(categories=['primary']))
    contains_results = repo.find(params=QueryBuilderParams(name='ha'))

    assert [item.rank for item in eq_results] == [2]
    assert {item.rank for item in in_results} == {1, 3}
    assert {item.name for item in contains_results} == {'alpha', 'charlie'}
