from sqlalchemy import Integer, String, desc, event, select
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import Mapped, mapped_column
import pytest

from repom.models.base_model import BaseModel

pytestmark = pytest.mark.asyncio


class RepositoryOrderingModel(BaseModel):
    __tablename__ = "repository_ordering_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sort_value: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(100))


class CompositeRepositoryOrderingModel(BaseModel):
    __tablename__ = "composite_repository_ordering_items"

    use_id = False

    part_a: Mapped[int] = mapped_column("db_part_a", Integer, primary_key=True)
    part_b: Mapped[str] = mapped_column("db_part_b", String(20), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))


def _make_repository(repository_adapter, model=RepositoryOrderingModel):
    repository = repository_adapter.repository_class(model, repository_adapter.session)
    repository.allowed_order_columns = ["id", "sort_value", "label", "rating"]
    return repository


async def _call(repository_adapter, method, *args, **kwargs):
    return await repository_adapter.call(method, *args, **kwargs)


async def test_string_ordering_adds_primary_key_and_pages_without_duplicates(repository_adapter):
    repository = _make_repository(repository_adapter)
    rows = [
        RepositoryOrderingModel(sort_value=5, label=f"row-{index}")
        for index in range(5)
    ]
    for row in rows:
        await _call(repository_adapter, repository.save, row)

    statement = repository.set_find_option(
        select(RepositoryOrderingModel),
        order_by="sort_value:desc",
        limit=2,
    )
    sql = str(statement.compile(dialect=sqlite.dialect()))
    assert "ORDER BY repository_ordering_items.sort_value DESC, repository_ordering_items.id DESC" in sql

    repository.default_order_by = "sort_value:desc"
    default_statement = repository.set_find_option(
        select(RepositoryOrderingModel),
        limit=2,
    )
    default_sql = str(default_statement.compile(dialect=sqlite.dialect()))
    assert "ORDER BY repository_ordering_items.sort_value DESC, repository_ordering_items.id DESC" in default_sql

    pages = []
    for offset in range(0, len(rows), 2):
        pages.extend(
            await _call(
                repository_adapter,
                repository.find,
                order_by="sort_value:desc",
                limit=2,
                offset=offset,
            )
        )

    page_ids = [row.id for row in pages]
    assert page_ids == [row.id for row in reversed(rows)]
    assert len(page_ids) == len(set(page_ids)) == len(rows)


async def test_ordering_by_primary_key_does_not_repeat_the_key(repository_adapter):
    repository = _make_repository(repository_adapter)

    statement = repository.set_find_option(
        select(RepositoryOrderingModel),
        order_by="id:desc",
    )
    sql = str(statement.compile(dialect=sqlite.dialect()))

    assert sql.count("repository_ordering_items.id DESC") == 1


async def test_default_order_uses_every_composite_primary_key_attribute(repository_adapter):
    repository = _make_repository(repository_adapter, CompositeRepositoryOrderingModel)
    rows = [
        CompositeRepositoryOrderingModel(part_a=2, part_b="b", label="last"),
        CompositeRepositoryOrderingModel(part_a=1, part_b="c", label="third"),
        CompositeRepositoryOrderingModel(part_a=1, part_b="a", label="first"),
    ]
    for row in rows:
        await _call(repository_adapter, repository.save, row)

    statement = repository.set_find_option(
        select(CompositeRepositoryOrderingModel),
        limit=10,
    )
    sql = str(statement.compile(dialect=sqlite.dialect()))
    assert "ORDER BY composite_repository_ordering_items.db_part_a ASC, composite_repository_ordering_items.db_part_b ASC" in sql

    results = await _call(repository_adapter, repository.find, limit=10)
    assert [(row.part_a, row.part_b) for row in results] == [
        (1, "a"),
        (1, "c"),
        (2, "b"),
    ]


async def test_single_get_by_uses_primary_key_even_with_virtual_default_order(repository_adapter):
    repository = _make_repository(repository_adapter)
    repository.default_order_by = "rating:desc"
    repository.virtual_order_columns = ["rating"]
    rows = [
        RepositoryOrderingModel(id=40, sort_value=5, label="higher"),
        RepositoryOrderingModel(id=12, sort_value=5, label="lower"),
    ]
    for row in rows:
        await _call(repository_adapter, repository.save, row)

    statements = []
    session = repository_adapter.session
    event_session = session.sync_session if repository_adapter.mode == "async" else session

    def capture_statement(execute_state):
        statements.append(execute_state.statement)

    event.listen(event_session, "do_orm_execute", capture_statement)
    try:
        result = await _call(
            repository_adapter,
            repository.get_by,
            "sort_value",
            5,
            single=True,
        )
        by_id = await _call(repository_adapter, repository.get_by_id, 12)
    finally:
        event.remove(event_session, "do_orm_execute", capture_statement)

    assert result.id == 12
    sql = str(statements[0].compile(dialect=sqlite.dialect()))
    assert "ORDER BY repository_ordering_items.id ASC" in sql
    assert "rating" not in sql
    by_id_sql = str(statements[1].compile(dialect=sqlite.dialect()))
    assert "ORDER BY" not in by_id_sql
    assert by_id.id == 12


async def test_expression_ordering_defines_the_complete_order(repository_adapter):
    repository = _make_repository(repository_adapter)

    expression_statement = repository.set_find_option(
        select(RepositoryOrderingModel),
        order_by=desc(RepositoryOrderingModel.sort_value),
    )
    expression_sql = str(expression_statement.compile(dialect=sqlite.dialect()))
    assert "ORDER BY repository_ordering_items.sort_value DESC" in expression_sql
    assert "repository_ordering_items.id DESC" not in expression_sql

    sequence_statement = repository.set_find_option(
        select(RepositoryOrderingModel),
        order_by=(
            RepositoryOrderingModel.sort_value.asc(),
            RepositoryOrderingModel.id.desc(),
        ),
    )
    sequence_sql = str(sequence_statement.compile(dialect=sqlite.dialect()))
    assert "ORDER BY repository_ordering_items.sort_value ASC, repository_ordering_items.id DESC" in sequence_sql


async def test_string_ordering_sequences_respect_allowlist(repository_adapter):
    repository = _make_repository(repository_adapter)
    repository.allowed_order_columns = ["id"]

    with pytest.raises(ValueError, match="not allowed for sorting"):
        repository.set_find_option(
            select(RepositoryOrderingModel),
            order_by=["sort_value:desc"],
        )

    repository.default_order_by = ("sort_value:desc",)
    with pytest.raises(ValueError, match="not allowed for sorting"):
        repository.set_find_option(select(RepositoryOrderingModel))


async def test_string_entries_in_ordering_sequences_are_parsed(repository_adapter):
    repository = _make_repository(repository_adapter)
    order_by = ["sort_value:desc", "id:asc"]

    statement = repository.set_find_option(
        select(RepositoryOrderingModel),
        order_by=order_by,
    )
    sql = str(statement.compile(dialect=sqlite.dialect()))

    assert "ORDER BY repository_ordering_items.sort_value DESC, repository_ordering_items.id ASC" in sql

    repository.default_order_by = order_by
    default_statement = repository.set_find_option(select(RepositoryOrderingModel))
    default_sql = str(default_statement.compile(dialect=sqlite.dialect()))

    assert "ORDER BY repository_ordering_items.sort_value DESC, repository_ordering_items.id ASC" in default_sql
