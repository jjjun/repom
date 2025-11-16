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
from repom.db import Base
from repom.db import db_session


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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # key ユニークな英字列を入れる(ex. taro, hanako, ...)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default='')

    __table_args__ = (
        CheckConstraint("key != ''", name='key_not_empty'),
    )


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
    """
    sample_data = generate_sample_roster_data(SAVE_COUNT)

    save_model_instances(RosterModel, sample_data, db_session)

    # save_model_instancesにより、既にデータは保存されている
    # この先の処理では事前にキーをチェックして、既に存在している為、保存はスキップされる
    try:
        for item in sample_data:
            try:
                instance = RosterModel(**item)
                db_session.add(instance)
                db_session.commit()
            except IntegrityError as e:
                # トランザクションをロールバックし、データベースの一貫性を保たないといけないみたい
                # この処理をしないと `sqlalchemy.exc.PendingRollbackError` が起こる。
                db_session.rollback()
                pass

    except Exception as e:
        db_session.rollback()
        raise e


def test_check_duplicate_key_and_skip(db_test):
    """
    上記よりもスッキリかけるし、`.commit()` の回数を1回に出来るので、こっちの方が良い。
    """
    sample_data = generate_sample_roster_data(SAVE_COUNT)

    save_model_instances(RosterModel, sample_data, db_session)

    # save_model_instancesにより、既にデータは保存されている
    # この先の処理では事前にキーをチェックして、既に存在している為、保存はスキップされる
    try:
        for item in sample_data:
            # 事前にキーをチェックして、既に存在している場合はスキップする
            existing_item = db_session.query(RosterModel).filter_by(key=item['key']).first()
            if existing_item:
                continue

            instance = RosterModel(**item)
            db_session.add(instance)

        db_session.commit()

    except Exception as e:
        db_session.rollback()
        raise e
