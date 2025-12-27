from tests._init import *
from sqlalchemy import Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import StatementError
from repom.custom_types.ListJSON import ListJSON, listjson_filter
from repom.base_model import BaseModel
from repom.repositories import BaseRepository
from repom.repositories._core import FilterParams
from typing import Optional, List


class ListModel(BaseModel):
    __tablename__ = 'test_model_listjson'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    option_list: Mapped[List] = mapped_column(ListJSON)


class ListModelFilterParams(FilterParams):
    option_list: Optional[List[str]] = None


class ListModelRepository(BaseRepository[ListModel]):
    def __init__(self, session):
        super().__init__(ListModel, session)

    def find(self, params: ListModelFilterParams, **kwargs):
        filters = []
        if params.option_list is not None:
            filters.extend(listjson_filter(self.model.option_list, params.option_list))
        return super().find(filters=filters, **kwargs)


def test_list_json_default_empty_list(db_test):
    log = ListModel()
    db_test.add(log)
    db_test.commit()
    assert log.option_list == []


def test_list_json_raises_error_on_non_list(db_test):
    with pytest.raises(StatementError):
        log = ListModel(option_list={"key": "value"})
        db_test.add(log)
        db_test.commit()


def test_list_json_retrieves_as_list(db_test):
    option_data = ["item1", "item2"]
    log = ListModel(option_list=option_data)
    db_test.add(log)
    db_test.commit()
    retrieved_log = db_test.query(ListModel).filter_by(id=log.id).first()
    assert isinstance(retrieved_log.option_list, list)
    assert retrieved_log.option_list == option_data


def test_listjson_find_by_option_list(db_test):
    repo = ListModelRepository(session=db_test)
    # データを追加
    log1 = ListModel(option_list=["foo", "bar"])
    log2 = ListModel(option_list=["baz", "qux"])
    log3 = ListModel(option_list=["foo", "baz"])
    db_test.add_all([log1, log2, log3])
    db_test.commit()

    # "foo" を含むものを検索
    results = repo.find(ListModelFilterParams(option_list=["foo"]))
    ids = [log.id for log in results]
    assert log1.id in ids
    assert log3.id in ids
    assert log2.id not in ids

    # "baz" を含むものを検索
    results = repo.find(ListModelFilterParams(option_list=["baz"]))
    ids = [log.id for log in results]
    assert log2.id in ids
    assert log3.id in ids
    assert log1.id not in ids

    # "bar" と "foo" の両方を含むもの（AND検索）
    results = repo.find(ListModelFilterParams(option_list=["foo", "bar"]))
    ids = [log.id for log in results]
    assert log1.id in ids
    assert log2.id not in ids
    assert log3.id not in ids


def test_listjson_find_empty_option_list(db_test):
    """Test that searching with option_list=[] returns only records with an empty list."""
    repo = ListModelRepository(session=db_test)
    # データを追加
    log1 = ListModel(option_list=["foo"])
    log2 = ListModel(option_list=[])
    log3 = ListModel(option_list=["bar"])
    db_test.add_all([log1, log2, log3])
    db_test.commit()

    # 空リストで検索
    results = repo.find(ListModelFilterParams(option_list=[]))
    ids = [log.id for log in results]
    assert log2.id in ids
    assert log1.id not in ids
    assert log3.id not in ids
