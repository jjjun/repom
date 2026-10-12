import pytest
from pydantic import ConfigDict, ValidationError

from repom.repositories import AsyncBaseRepository, BaseRepository, FilterParams
from tests.fixtures.models import SimpleRecord


class NameFilterParams(FilterParams):
    name: str | None = None


class NameFilterRepository(BaseRepository[SimpleRecord]):
    field_to_column = {"name": SimpleRecord.name}


class AsyncNameFilterRepository(AsyncBaseRepository[SimpleRecord]):
    field_to_column = {"name": SimpleRecord.name}


class CustomPagingFilterParams(FilterParams):
    limit: int | None = None
    offset: int | None = None
    order_by: str | None = None
    name: str | None = None


class CustomPagingFilterRepository(BaseRepository[SimpleRecord]):
    def _build_filters(self, params: FilterParams | None) -> list:
        if params is None:
            return []

        filters = []
        if params.name is not None:
            filters.append(SimpleRecord.name == params.name)
        if params.limit is not None:
            filters.append(SimpleRecord.id == params.limit)
        if params.offset is not None:
            filters.append(SimpleRecord.id > params.offset)
        if params.order_by is not None:
            filters.append(SimpleRecord.name == params.order_by)
        return filters


class AttributeFilterParams(FilterParams):
    model_config = ConfigDict(from_attributes=True)
    name: str


class FilterParamsAttributes:
    name = "match"
    limit = 10


@pytest.mark.parametrize("option_name", ("limit", "offset", "order_by"))
def test_filter_params_rejects_undeclared_find_options(option_name):
    with pytest.raises(ValidationError, match=option_name):
        NameFilterParams.model_validate({"name": "match", option_name: 10})


def test_filter_params_still_ignores_non_reserved_extra_fields():
    params = NameFilterParams(name="match", unrelated="ignored")

    assert params.model_dump() == {"name": "match"}
    assert params.model_extra is None


def test_filter_params_passes_non_mapping_input_to_pydantic():
    params = AttributeFilterParams.model_validate(FilterParamsAttributes())

    assert params.name == "match"


def test_declared_find_options_work_with_custom_filter_builder(db_test):
    repo = CustomPagingFilterRepository(session=db_test)
    record = repo.save(SimpleRecord(name="match"))
    params = CustomPagingFilterParams(
        limit=record.id,
        offset=0,
        order_by="match",
        name="match",
    )

    assert repo.find(params=params, limit=10) == [record]
    assert repo.count(params=params) == 1


def test_find_and_count_accept_valid_filter_params(db_test):
    repo = NameFilterRepository(session=db_test)
    repo.saves([SimpleRecord(name="match"), SimpleRecord(name="other")])
    params = NameFilterParams(name="match")

    assert [record.name for record in repo.find(params=params, limit=10)] == ["match"]
    assert repo.count(params=params) == 1


@pytest.mark.asyncio
async def test_async_find_and_count_accept_valid_filter_params(async_db_test):
    repo = AsyncNameFilterRepository(session=async_db_test)
    await repo.saves([SimpleRecord(name="match"), SimpleRecord(name="other")])
    params = NameFilterParams(name="match")

    assert [record.name for record in await repo.find(params=params, limit=10)] == ["match"]
    assert await repo.count(params=params) == 1
