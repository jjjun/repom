# Python プログラムが終了する際に特定の関数を自動的に呼び出すための機能を提供するモジュール
# プログラムの終了時にリソースのクリーンアップやその他の終了処理を行う
import atexit

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import scoped_session, sessionmaker
# SQLAlchemyのバージョン2.0以降では declarative_base の場所が変わっている
# sqlalchemy.ext.declarative -> sqlalchemy.orm
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base

from repom.config import config

engine = create_engine(config.db_url, **config.engine_kwargs)

inspector = inspect(engine)

"""
scoped_session
 スレッドローカルなセッションを提供するためのヘルパークラスです。
 これを使用すると、スレッドごとに独立したセッションを持つことができます。

sessionmaker
 SQLAlchemy の ORM セッションファクトリです。
 これを使用して、セッションのインスタンスを作成します。
 セッションはデータベース接続の管理と ORM オブジェクトとの対話を担当します。
 autocommit=False:
  セッションは自動的にコミットしません。明示的に commit() を呼び出す必要があります。
 autoflush=False:
  トランザクションがコミットされる前に、変更されたオブジェクトをデータベースにフラッシュしません。
  必要に応じて flush() を呼び出して手動でフラッシュすることができます。
 bind=engine:
  セッションが使用するデータベースエンジンを指定します。
"""
# スレッドローカルな scoped_session (既存の db_session)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# 新規セッションを生成する sessionmaker インスタンス
# 各呼び出しで新しいセッションを作成するために使用
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """新しいセッションインスタンスを取得"""
    return sessionmaker(bind=engine)()


"""
declarative_base
 SQLAlchemy ORM (Object-Relational Mapping) の一部で、
 データベースのテーブルとPythonクラスをマッピングするための基底クラスを作成するために使用されます。
 この基底クラスを継承することで、データベースのテーブルを表すクラスを定義できます。
"""
Base = declarative_base()

"""
query_property()

SQLAlchemy ORMの便利な機能の1つ。

query_propertyは、デフォルトのクエリオブジェクトを提供するためのプロパティを設定する。
このプロパティを設定することで、各モデルクラスから直接クエリを実行出来る。
具体的には、次のような記述が出来るようになる。

all_users = User.query.all()
"""
Base.query = db_session.query_property()


def shutdown_session(exception=None):
    """
    クリーンアップ処理
    """
    db_session.remove()


"""
アプリケーションの終了時にセッションをクリーンアップする
atexit.register 関数を使用して、プログラム終了時に実行したい関数を登録します。
登録された関数は、プログラムが正常に終了する際に自動的に呼び出されます。
"""
atexit.register(shutdown_session)

# エクスポート対象
__all__ = [
    'engine',
    'inspector',
    'db_session',
    'SessionLocal',
    'get_session',
    'Base',
    'shutdown_session',
]
