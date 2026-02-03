from tests._init import *
import pytest
from typing import List, Type, Optional
from datetime import datetime, timedelta, date as date_type
from sqlalchemy.orm import Session, Mapped, mapped_column
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Date,
    text,
)
from repom.database import get_sync_engine, get_inspector, get_db_session, Base


"""
SQLiteにはDateTime型やDate型は無い。
日付や日時のデータを保持する際、データは TEXT、REAL、INTEGER型 になる。

しかし、sqlalchemyのモデルを定義する時には `Date` や `DateTime` と言った型を設定できる。
sqlalchemy の方で型を設定すると、SQLite自体、内部ではTEXTとしてデータを扱うんだけど、
実際の使用感に関しては `DateTime` 等、日付型と同じ使用感になる(sqlalchemy経由でsqliteを操作する為)。
例えば、日付型のカラムに適当な文字を入れるとエラーが発生する。

このメモでは、sqlite+sqlalchemy環境で `Date` や `DateTime` はどのような挙動をするかのメモ。

現在、次のような事を書いてる。

- 日付型のカラムに適当な文字を入れるとエラーが発生する事
- カラムを文字型にした場合、日付の範囲指定する検索に問題が出るか否か
- 日付を保存する時の、Date型 と DateTime型 の違い

サンプルモデルとして次を用意
"""


# Module-level model definitions removed - each test function defines its own local models
# to avoid mapper interference (see Issue #021)


def generate_test_data(model: Type, start_date: datetime, end_date: datetime, num_records: int) -> List:
    """
    Generate a specified number of records with dates ranging from start_date to end_date.

    # Example usage:
    start = datetime(2023, 12, 1)
    end = datetime(2024, 2, 20, 23, 59, 59)
    records = generate_test_data(TaskDateModel, start, end, 100)

    :param model: The model class to generate data for (TaskDateModel or TaskStringModel)
    :param start_date: The start date for the range
    :param end_date: The end date for the range
    :param num_records: The number of records to generate
    :return: A list of generated model instances
    """
    delta = (end_date - start_date) / num_records
    records = []
    for i in range(num_records):
        record_date = start_date + i * delta
        record = model(name='take a bath', created_at=record_date)
        records.append(record)
    return records


# poetry run pytest tests/behavior_tests/test_date_type_comparison.py::test_compare_save_behavior
def test_compare_save_behavior(db_test):
    """
    TaskDateModel と TaskStringModel にデータを保存した際、日付の挙動の違いを確認する。
    保存時の挙動の違いは次の様になった。

    TaskDateModel
     done_at = Date
     created_at = DateTime
    TaskStringModel
     done_at = String
     created_at = String

    注意点.
    commit 前では TaskStringModel.done_at は `datetime.date` だけど、commit した後は `str` となる。
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers

    # Redefine models within test to handle clear_mappers() from other tests
    class LocalTaskModel(Base):
        __abstract__ = True
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(255), default='')

        def done(self):
            self.done_at = datetime.now().date()

    class LocalTaskDateModel(LocalTaskModel):
        __tablename__ = 'task_date'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[date_type]] = mapped_column(Date)
        created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now())

    class LocalTaskStringModel(LocalTaskModel):
        __tablename__ = 'task_string'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[str]] = mapped_column(String)
        created_at: Mapped[Optional[str]] = mapped_column(String, default=datetime.now())

    Base.metadata.create_all(bind=db_test.bind)

    task_name = 'take a bath'
    task_date = LocalTaskDateModel(name=task_name)
    task_string = LocalTaskStringModel(name=task_name)
    task_date.done()
    task_string.done()

    # ==========
    # commit前では `task_string.done_at` は `datetime.date`
    # ==========
    print("\n\n----- before commit -----")
    print(type(task_date.done_at))    # <class 'datetime.date'>
    print(type(task_string.done_at))  # <class 'datetime.date'>
    print('----- /before commit -----')

    db_test.add_all([task_date, task_string])
    db_test.commit()

    # ==========
    # commit後では `task_string.done_at` は `str`
    # ==========
    print('----- after commit -----')
    print(type(task_date.done_at))       # <class 'datetime.date'>
    print(type(task_date.created_at))    # <class 'datetime.datetime'>
    print(type(task_string.done_at))     # <class 'str'>
    print(type(task_string.created_at))  # <class 'str'>
    print('----- /after commit -----')

    # Cleanup mappers to prevent SAWarning in subsequent tests
    clear_mappers()
    configure_mappers()


# poetry run pytest tests/behavior_tests/test_date_type_comparison.py::test_handle_invalid_date_save
def test_handle_invalid_date_save(db_test):
    """
    TaskDateModel.created_at と TaskStringModel.created_at に違反したデータを保存する。
    違反データ保存時の挙動の違いは次の様になった。

    TaskDateModel
     エラーが発生。
     sqlalchemy.exc.StatementError: (builtins.TypeError) 
     SQLite DateTime type only accepts Python datetime and date objects as input.
    TaskStringModel
     エラーは発生せず、文字列を含んだ値が保存される(例.2023-12-23 ffds)

    """
    from sqlalchemy.orm import clear_mappers, configure_mappers

    # Redefine models within test to handle clear_mappers() from other tests
    class LocalTaskModel(Base):
        __abstract__ = True
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(255), default='')

    class LocalTaskDateModel(LocalTaskModel):
        __tablename__ = 'task_date'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[date_type]] = mapped_column(Date)
        created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now())

    class LocalTaskStringModel(LocalTaskModel):
        __tablename__ = 'task_string'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[str]] = mapped_column(String)
        created_at: Mapped[Optional[str]] = mapped_column(String, default=datetime.now())

    Base.metadata.create_all(bind=db_test.bind)

    task_name = 'take a bath'
    invalid_date = '2023-12-23 ffds'
    task_date = LocalTaskDateModel(name=task_name, created_at=invalid_date)
    task_string = LocalTaskStringModel(name=task_name, created_at=invalid_date)

    # TaskDateModel に違反データを保存するとエラーが出る
    try:
        db_test.add(task_date)
        # commit() するとエラーが発生する
        db_test.commit()
    except Exception as e:
        db_test.rollback()
        print('\n\n----- error -----')
        print(e)
        print('----- /error -----')

    # TaskStringModel に違反データを保存してもエラーは出ない
    try:
        db_test.add(task_string)
        db_test.commit()
        print('\n\n----- no error -----')
        print(task_string.created_at)
        print('----- no error -----')
    except Exception as e:
        db_test.rollback()
        raise e

    # Cleanup mappers to prevent SAWarning in subsequent tests
    clear_mappers()
    configure_mappers()


# poetry run pytest tests/behavior_tests/test_date_type_comparison.py::test_compare_search_behavior
def test_compare_search_behavior(db_test):
    """
    辞書型のデータを保存する
    """
    from sqlalchemy.orm import clear_mappers, configure_mappers

    # Redefine models within test to handle clear_mappers() from other tests
    class LocalTaskModel(Base):
        __abstract__ = True
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(255), default='')

    class LocalTaskDateModel(LocalTaskModel):
        __tablename__ = 'task_date'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[date_type]] = mapped_column(Date)
        created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now())

    class LocalTaskStringModel(LocalTaskModel):
        __tablename__ = 'task_string'
        __table_args__ = {'extend_existing': True}
        done_at: Mapped[Optional[str]] = mapped_column(String)
        created_at: Mapped[Optional[str]] = mapped_column(String, default=datetime.now())

    Base.metadata.create_all(bind=db_test.bind)

    search_start = datetime(2023, 12, 1)
    search_end = datetime(2024, 2, 20, 23, 59, 59)
    task_records = generate_test_data(LocalTaskDateModel, search_start, search_end, 20)
    task_str_records = generate_test_data(LocalTaskStringModel, search_start, search_end, 20)
    db_test.add_all(task_records)
    db_test.add_all(task_str_records)

    out_range_start = datetime(2020, 12, 1)
    out_range_end = datetime(2021, 2, 20, 23, 59, 59)
    task_records = generate_test_data(LocalTaskDateModel, out_range_start, out_range_end, 10)
    task_str_records = generate_test_data(LocalTaskStringModel, out_range_start, out_range_end, 10)
    db_test.add_all(task_records)
    db_test.add_all(task_str_records)

    db_test.commit()

    task_date_results = db_test.query(LocalTaskDateModel).filter(
        LocalTaskDateModel.created_at >= search_start,
        LocalTaskDateModel.created_at <= search_end
    ).all()
    task_str_results = db_test.query(LocalTaskStringModel).filter(
        LocalTaskStringModel.created_at >= search_start,
        LocalTaskStringModel.created_at <= search_end
    ).all()
    print("\n\n----- search results -----")
    print('TaskDateModel: %i' % len(task_date_results))
    print('TaskStrModel: %i' % len(task_str_results))
    print('TaskDateModel: %s' % task_date_results[0].created_at)
    print('TaskStrModel: %s' % task_str_results[0].created_at)
    print("----- search results -----")

    task_date_results = db_test.query(LocalTaskDateModel).filter(
        LocalTaskDateModel.created_at.between(search_start, search_end)
    ).all()
    task_str_results = db_test.query(LocalTaskStringModel).filter(
        LocalTaskStringModel.created_at.between(search_start, search_end)
    ).all()
    print("\n\n----- search results -----")
    print('TaskDateModel: %i' % len(task_date_results))
    print('TaskStrModel: %i' % len(task_str_results))
    print('TaskDateModel: %s' % task_date_results[0].created_at)
    print('TaskStrModel: %s' % task_str_results[0].created_at)
    print("----- search results -----")

    # クエリの実行
    task_date_results = db_test.execute(text("""
        SELECT * FROM task_date
        WHERE created_at BETWEEN :start_date AND :end_date
    """), {'start_date': search_start, 'end_date': search_end}).fetchall()

    task_str_results = db_test.execute(text("""
        SELECT * FROM task_string
        WHERE created_at BETWEEN :start_date AND :end_date
    """), {'start_date': search_start, 'end_date': search_end}).fetchall()

    print("\n\n----- search results -----")
    print('TaskDateModel: %i' % len(task_date_results))
    print('TaskStrModel: %i' % len(task_str_results))
    print('TaskDateModel: %s' % task_date_results[0].created_at)
    print('TaskStrModel: %s' % task_str_results[0].created_at)
    print("----- search results -----")

    task_date_results = db_test.execute(text("""
        SELECT * FROM task_date
        WHERE created_at >= :start_date AND created_at <= :end_date
    """), {'start_date': search_start, 'end_date': search_end}).fetchall()

    task_str_results = db_test.execute(text("""
        SELECT * FROM task_string
        WHERE created_at >= :start_date AND created_at <= :end_date
    """), {'start_date': search_start, 'end_date': search_end}).fetchall()

    print("\n\n----- search results -----")
    print('TaskDateModel: %i' % len(task_date_results))
    print('TaskStrModel: %i' % len(task_str_results))
    print('TaskDateModel: %s' % task_date_results[0].created_at)
    print('TaskStrModel: %s' % task_str_results[0].created_at)
    print("----- search results -----")

    # Cleanup mappers to prevent SAWarning in subsequent tests
    clear_mappers()
    configure_mappers()
