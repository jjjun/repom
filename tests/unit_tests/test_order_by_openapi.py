from tests._init import *

from sqlalchemy import Integer, String, desc
from sqlalchemy.orm import Mapped, mapped_column
import pytest

from repom import (
    BaseRepository,
    AsyncBaseRepository,
    build_order_by_query_depends,
    get_order_by_columns,
    get_order_by_default_value,
    get_order_by_values,
    VirtualColumnError,
)
from repom.models.base_model import BaseModel


try:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


class OrderByOpenAPIModel(BaseModel):
    __tablename__ = "order_by_openapi_items"

    name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)


class OrderByRepository(BaseRepository[OrderByOpenAPIModel]):
    allowed_order_columns = ["id", "name", "priority", "title", "created_at"]
    default_order_by = "priority:desc"

    def __init__(self, session):
        super().__init__(OrderByOpenAPIModel, session)


class AsyncOrderByRepository(AsyncBaseRepository[OrderByOpenAPIModel]):
    allowed_order_columns = ["id", "name", "priority", "title", "created_at"]
    default_order_by = "priority:desc"

    def __init__(self, session):
        super().__init__(OrderByOpenAPIModel, session)


class ExpressionOrderByRepository(BaseRepository[OrderByOpenAPIModel]):
    allowed_order_columns = ["id", "name", "priority"]
    default_order_by = desc(OrderByOpenAPIModel.priority)

    def __init__(self, session):
        super().__init__(OrderByOpenAPIModel, session)


class BareDefaultOrderRepository(BaseRepository[OrderByOpenAPIModel]):
    allowed_order_columns = ["id", "name", "priority"]
    default_order_by = "priority"

    def __init__(self, session):
        super().__init__(OrderByOpenAPIModel, session)


class VirtualOrderByRepository(BaseRepository[OrderByOpenAPIModel]):
    allowed_order_columns = ["id", "name", "priority", "rating"]
    virtual_order_columns = ["rating"]
    default_order_by = "priority:desc"

    def __init__(self, session):
        super().__init__(OrderByOpenAPIModel, session)


class InvalidVirtualOrderByRepository(BaseRepository[OrderByOpenAPIModel]):
    allowed_order_columns = ["id", "name", "priority"]
    virtual_order_columns = ["rating"]

    def __init__(self, session):
        super().__init__(OrderByOpenAPIModel, session)


def _find_enum_schemas(node, matches: list):
    if isinstance(node, dict):
        if "enum" in node:
            matches.append(node["enum"])
        for value in node.values():
            _find_enum_schemas(value, matches)
    elif isinstance(node, list):
        for item in node:
            _find_enum_schemas(item, matches)


def test_get_order_by_columns_filters_to_real_model_columns():
    assert get_order_by_columns(OrderByRepository) == [
        "id",
        "name",
        "priority",
    ]


def test_get_order_by_values_returns_canonical_pairs():
    assert get_order_by_values(OrderByRepository) == [
        "id:asc",
        "id:desc",
        "name:asc",
        "name:desc",
        "priority:asc",
        "priority:desc",
    ]


def test_get_order_by_values_supports_async_repository_classes():
    assert get_order_by_values(AsyncOrderByRepository) == get_order_by_values(
        OrderByRepository
    )


def test_get_order_by_columns_includes_virtual_columns():
    assert get_order_by_columns(VirtualOrderByRepository) == [
        "id",
        "name",
        "priority",
        "rating",
    ]


def test_get_order_by_columns_rejects_virtual_columns_outside_allowed_list():
    with pytest.raises(
        ValueError,
        match="virtual_order_columns must also be present in allowed_order_columns",
    ):
        get_order_by_columns(InvalidVirtualOrderByRepository)


def test_get_order_by_values_includes_virtual_columns():
    assert get_order_by_values(VirtualOrderByRepository) == [
        "id:asc",
        "id:desc",
        "name:asc",
        "name:desc",
        "priority:asc",
        "priority:desc",
        "rating:asc",
        "rating:desc",
    ]


def test_get_order_by_default_value_returns_canonical_string():
    assert get_order_by_default_value(OrderByRepository) == "priority:desc"


def test_get_order_by_default_value_ignores_sqlalchemy_expression():
    assert get_order_by_default_value(ExpressionOrderByRepository) is None


def test_get_order_by_default_value_rejects_bare_column_defaults():
    with pytest.raises(
        ValueError,
        match="canonical format 'column:asc' or 'column:desc'",
    ):
        get_order_by_default_value(BareDefaultOrderRepository)


def test_parse_order_by_rejects_bare_column_input(db_test):
    repo = OrderByRepository(session=db_test)
    repo.save(OrderByOpenAPIModel(name="alpha", priority=1))

    with pytest.raises(
        ValueError,
        match="canonical format 'column:asc' or 'column:desc'",
    ):
        repo.find(order_by="priority")


def test_parse_order_by_raises_virtual_column_error(db_test):
    repo = VirtualOrderByRepository(session=db_test)

    with pytest.raises(VirtualColumnError) as exc_info:
        repo.parse_order_by(OrderByOpenAPIModel, "rating:desc")

    assert exc_info.value.column_name == "rating"
    assert exc_info.value.direction == "desc"


def test_default_order_by_rejects_bare_column_default_at_runtime(db_test):
    repo = BareDefaultOrderRepository(session=db_test)
    repo.save(OrderByOpenAPIModel(name="alpha", priority=1))

    with pytest.raises(
        ValueError,
        match="canonical format 'column:asc' or 'column:desc'",
    ):
        repo.find()


@pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI is not installed. Install with: poetry add --group dev fastapi httpx",
)
def test_build_order_by_query_depends_returns_default_dict_shape():
    app = FastAPI()

    @app.get("/items")
    def read_items(
        order_params: dict = Depends(build_order_by_query_depends(OrderByRepository)),
    ):
        return order_params

    client = TestClient(app)

    assert client.get("/items").json() == {"order_by": "priority:desc"}
    assert client.get("/items?order_by=name:asc").json() == {"order_by": "name:asc"}


@pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI is not installed. Install with: poetry add --group dev fastapi httpx",
)
def test_build_order_by_query_depends_exposes_enum_in_openapi():
    app = FastAPI()

    @app.get("/items")
    def read_items(
        order_params: dict = Depends(build_order_by_query_depends(OrderByRepository)),
    ):
        return order_params

    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    enum_matches = []
    _find_enum_schemas(schema, enum_matches)

    assert [
        "id:asc",
        "id:desc",
        "name:asc",
        "name:desc",
        "priority:asc",
        "priority:desc",
    ] in enum_matches

    operation = schema["paths"]["/items"]["get"]
    parameters = operation["parameters"]
    order_by_param = next(param for param in parameters if param["name"] == "order_by")
    assert order_by_param["required"] is False


@pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI is not installed. Install with: poetry add --group dev fastapi httpx",
)
def test_build_order_by_query_depends_exposes_virtual_enum_in_openapi():
    app = FastAPI()

    @app.get("/items")
    def read_items(
        order_params: dict = Depends(
            build_order_by_query_depends(VirtualOrderByRepository)
        ),
    ):
        return order_params

    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    enum_matches = []
    _find_enum_schemas(schema, enum_matches)

    assert [
        "id:asc",
        "id:desc",
        "name:asc",
        "name:desc",
        "priority:asc",
        "priority:desc",
        "rating:asc",
        "rating:desc",
    ] in enum_matches


@pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI is not installed. Install with: poetry add --group dev fastapi httpx",
)
def test_build_order_by_query_depends_rejects_invalid_string_default():
    with pytest.raises(
        ValueError,
        match="canonical format 'column:asc' or 'column:desc'",
    ):
        build_order_by_query_depends(BareDefaultOrderRepository)
