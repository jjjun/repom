from tests._init import *
import warnings
from sqlalchemy import Integer, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import StatementError, SAWarning
from repom.custom_types.ListJSON import ListJSON, listjson_filter
from repom.models.base_model import BaseModel
from repom.repositories import BaseRepository
from repom.repositories._core import FilterParams
from typing import Optional, List


class ListModel(BaseModel):
    __tablename__ = 'test_model_listjson'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    option_list: Mapped[List] = mapped_column(ListJSON)


@pytest.fixture(scope='function', autouse=True)
def setup_tables(setup_database_tables):
    """setup_database_tables に依存して、テーブルが作成されることを保証"""
    pass


class ListModelFilterParams(FilterParams):
    option_list: Optional[List[str]] = None


class ListModelRepository(BaseRepository[ListModel]):
    def __init__(self, session):
        super().__init__(ListModel, session)

    def find(self, params=None, filters=None, include_deleted=False, **kwargs):
        own_filters = []
        if params is not None and params.option_list is not None:
            own_filters.extend(listjson_filter(self.model.option_list, params.option_list))
        merged_filters = [*own_filters, *(filters or [])]
        return super().find(filters=merged_filters, include_deleted=include_deleted, **kwargs)


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


def test_listjson_filter_compiles_json_array_elements_text_for_postgresql():
    """PostgreSQL の json_each()/json_each_text() は JSON オブジェクト専用で
    ListJSON の配列には使えない (cannot deconstruct an array as an object) ため、
    配列の要素展開には json_array_elements_text() を使うこと。"""
    filters = listjson_filter(ListModel.option_list, ["Action"])
    stmt = select(ListModel).filter(*filters)
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "json_array_elements_text(" in compiled
    assert "json_each(" not in compiled


def test_listjson_filter_compiles_json_each_for_sqlite():
    """SQLite には json_array_elements_text() が無いため、従来どおり json_each() を使うこと。"""
    filters = listjson_filter(ListModel.option_list, ["Action"])
    stmt = select(ListModel).filter(*filters)
    compiled = str(stmt.compile(dialect=sqlite.dialect()))
    assert "json_each(" in compiled
    assert "json_array_elements_text(" not in compiled


def test_listjson_filter_empty_list_compiles_json_array_length():
    """空リスト検索は json = json 比較ではなく json_array_length() = 0 を使うこと。"""
    filters = listjson_filter(ListModel.option_list, [])
    stmt = select(ListModel).filter(*filters)
    pg_compiled = str(stmt.compile(dialect=postgresql.dialect()))
    sqlite_compiled = str(stmt.compile(dialect=sqlite.dialect()))
    assert "json_array_length(" in pg_compiled
    assert "json_array_length(" in sqlite_compiled


def test_listjson_filter_empty_list_no_cache_warning_with_sqlalchemy_utils(db_test):
    """sqlalchemy_utils.expressions は inherit_cache 未設定の json_array_length を
    SQLAlchemy のグローバル関数レジストリに登録するため、同モジュールが
    プロセス内で import された状態で func.json_array_length(...) を使うと
    SQL コンパイルキャッシュが無効化され SAWarning が発生する。listjson_filter()
    の空リスト一致は専用の _ListjsonArrayLength を使うため、その import 後でも
    警告が出ないことを確認する。"""
    pytest.importorskip("sqlalchemy_utils.expressions")
    log = ListModel(option_list=[])
    db_test.add(log)
    db_test.commit()

    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        repo = ListModelRepository(session=db_test)
        results = repo.find(ListModelFilterParams(option_list=[]))
    ids = [item.id for item in results]
    assert log.id in ids
