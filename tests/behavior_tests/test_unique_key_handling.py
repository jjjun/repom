from tests._init import *
from sqlalchemy import (
    Integer,
    String,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError
from tests.utils import (
    generate_sample_roster_data,
    save_model_instances
)
from repom.database import Base, _db_manager
import pytest


@pytest.fixture(autouse=True)
def ensure_roster_model_ready():
    """Ensure RosterModel is properly initialized before each test.

    This fixture runs automatically before each test in this module.
    It ensures that RosterModel's mapper is valid, even if other tests
    have called clear_mappers().
    """
    from sqlalchemy.orm import configure_mappers
    # Force mapper configuration to ensure RosterModel is ready
    try:
        configure_mappers()
    except Exception:
        # If configure fails, it means mappers need to be rebuilt
        # This will be handled by the module reload in isolated_mapper_registry
        pass
    yield


"""
RosterModel において key がユニークキーとして設定されている
key にはユニークな英字列を入れることが前提となっていて、同じキー名が入った場合には例外が発生する

サンプルの前提として、保存するデータにはこのkeyが重複するデータが含まれている
そして、悩んでいる事が次の2つの方法

例外が発生したらスキップする:
 この処理には例外発生のオーバヘッドにより、パフォーマンスに問題があるのではないか?

事前にキーの重複をチェックする:
 この処理はデータベースにアクセスする回数が増えるので、パフォーマンスに問題があるのではないか?

chatGPT回答:
 事前にキーの重複をチェックする方法推奨。
 データベースにアクセスする回数が増える可能性がありますが、例外処理のオーバーヘッドを避けることができます。
 パフォーマンスの観点からは、キーの重複チェックを行う方が一般的に良いとされています。
"""


class RosterModel(Base):
    """RosterModel 
    授業の名簿を表す英単語は "Roster"
    特定のグループや組織のメンバーの名前、役割、担当業務、スケジュールなどが記載されたリストや表のこと
    """
    __tablename__ = 'rosters'
    __table_args__ = (
        CheckConstraint("key != ''", name='key_not_empty'),
        {'extend_existing': True}  # Allow table redefinition after clear_mappers()
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # key ユニークな英字列を入れる(ex. taro, hanako, ...)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default='')


# 結果
# ==========
SAVE_COUNT = 3000
# test_skip_on_exception 実行時間: 3.392377秒
# test_check_duplicate_key_and_skip 実行時間: 2.871075秒
# ==========


def test_skip_on_exception(db_test):
    """
    例外が発生したらスキップするの方法だと、`.add()` で追加した後に都度 `.commit()` をしなくてはいけない。
    何故ならユニーク重複のエラーが出るのは `.commit()` した段階だから。

    更に、ユニーク重複のエラーが出たら都度 `.rollback()` しなくてはいけないので、更にパフォーマンスが悪そう

    gpt:
    .add()メソッドは、オブジェクトをセッションに追加するだけで、実際にデータベースに対して変更を行うわけではありません。
    データベースに対する変更は、.commit()メソッドを呼び出したときに行われます。
    このときに、ユニーク制約違反などのデータベース制約がチェックされ、違反が発生した場合は例外がスローされます。

    Note: To handle clear_mappers() called by other tests, we redefine RosterModel
    within this test function.
    """
    # Redefine RosterModel within test to handle clear_mappers() from other tests
    from repom.database import Base
    from sqlalchemy import Integer, String, CheckConstraint
    from sqlalchemy.orm import Mapped, mapped_column

    class LocalRosterModel1(Base):
        __tablename__ = 'rosters'
        __table_args__ = (
            CheckConstraint("key != ''", name='key_not_empty'),
            {'extend_existing': True}
        )

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
        name: Mapped[str] = mapped_column(String(255), default='')

    # Ensure tables are created
    Base.metadata.create_all(bind=db_test.bind)

    sample_data = generate_sample_roster_data(SAVE_COUNT)
    save_model_instances(LocalRosterModel1, sample_data, db_test)

    # save_model_instancesにより、既にデータは保存されている
    # この先の処理では事前にキーをチェックして、既に存在している為、保存はスキップされる
    with _db_manager.get_sync_session() as session:
        try:
            for item in sample_data:
                try:
                    instance = LocalRosterModel1(**item)
                    session.add(instance)
                    session.commit()
                except IntegrityError as e:
                    # トランザクションをロールバックし、データベースの一貫性を保たないといけないみたい
                    # この処理をしないと `sqlalchemy.exc.PendingRollbackError` が起こる。
                    session.rollback()
                    pass

        except Exception as e:
            session.rollback()
            raise e


def test_check_duplicate_key_and_skip(db_test):
    """
    上記よりもスッキリかけるし、`.commit()` の回数を1回に出来るので、こっちの方が良い。
    """
    # Redefine RosterModel within test to handle clear_mappers() from other tests
    from repom.database import Base
    from sqlalchemy import Integer, String, CheckConstraint
    from sqlalchemy.orm import Mapped, mapped_column

    class LocalRosterModel2(Base):
        __tablename__ = 'rosters'
        __table_args__ = (
            CheckConstraint("key != ''", name='key_not_empty'),
            {'extend_existing': True}
        )

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
        name: Mapped[str] = mapped_column(String(255), default='')

    # Ensure tables are created
    Base.metadata.create_all(bind=db_test.bind)

    sample_data = generate_sample_roster_data(SAVE_COUNT)
    save_model_instances(LocalRosterModel2, sample_data, db_test)

    # save_model_instancesにより、既にデータは保存されている
    # この先の処理では事前にキーをチェックして、既に存在している為、保存はスキップされる
    try:
        for item in sample_data:
            # 事前にキーをチェックして、既に存在している場合はスキップする
            existing_item = db_test.query(LocalRosterModel2).filter_by(key=item['key']).first()
            if existing_item:
                continue

            instance = LocalRosterModel2(**item)
            db_test.add(instance)

        db_test.commit()

    except Exception as e:
        db_test.rollback()
        raise e
