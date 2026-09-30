
from sqlalchemy import Integer, String, desc
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.exc import UnmappedClassError
import pytest

from repom import (
    BaseRepository,
    AsyncBaseRepository,
    get_order_by_columns,
    get_order_by_default_value,
    get_order_by_values,
    VirtualColumnError,
)
from repom.models.base_model import BaseModel
from repom.repositories._order_by import normalize_order_by_value
import repom.repositories._order_by as order_by_module


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


class InvalidDefaultOrderRepository(BaseRepository[OrderByOpenAPIModel]):
    allowed_order_columns = ["id", "name", "priority"]
    default_order_by = "created_at:desc"


class UnmappedOrderByRepository(BaseRepository):
    pass


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


@pytest.mark.parametrize("order_by", [1, None, ["priority:desc"]])
def test_normalize_order_by_rejects_non_string_values(order_by):
    with pytest.raises(TypeError, match="must be a string"):
        normalize_order_by_value(order_by)


def test_normalize_order_by_rejects_missing_direction():
    with pytest.raises(ValueError, match="canonical format"):
        normalize_order_by_value("priority")


def test_normalize_order_by_rejects_unknown_direction():
    with pytest.raises(ValueError, match="Direction must be 'asc' or 'desc'"):
        normalize_order_by_value("priority:sideways")


def test_get_order_by_default_value_rejects_column_outside_allowlist():
    with pytest.raises(ValueError, match="is not valid"):
        get_order_by_default_value(InvalidDefaultOrderRepository)


def test_get_order_by_columns_rejects_unmapped_model():
    with pytest.raises(TypeError, match="Could not extract model"):
        get_order_by_columns(UnmappedOrderByRepository)


def test_get_order_by_columns_translates_unmapped_class_error(monkeypatch):
    def inspect_unmapped(_model_class):
        raise UnmappedClassError(BaseModel)

    monkeypatch.setattr(order_by_module, "sa_inspect", inspect_unmapped)

    with pytest.raises(TypeError, match="is not a mapped class"):
        get_order_by_columns(OrderByRepository)

pytestmark = pytest.mark.filterwarnings(
    r"ignore:find\(\) was called without a limit:RuntimeWarning"
)
