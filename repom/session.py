"""
セッション管理ユーティリティ

このモジュールは、SQLAlchemy セッションの管理を簡素化するためのヘルパー関数を提供します。
フレームワーク非依存な設計で、FastAPI、Flask、CLI など様々な環境で使用できます。
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from repom.db import SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """
    トランザクションなしのセッションを提供します。

    このジェネレータ関数は、FastAPI の Depends() などで使用できます。
    トランザクション管理は行わないため、明示的に commit() を呼ぶ必要があります。

    Yields:
        Session: SQLAlchemy セッション

    Example:
        >>> # FastAPI での使用例
        >>> @router.get("/items")
        >>> async def read_items(session: Session = Depends(get_db_session)):
        >>>     items = session.query(Item).all()
        >>>     return items
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db_transaction() -> Generator[Session, None, None]:
    """
    トランザクション管理付きのセッションを提供します。

    このジェネレータ関数は、自動的にトランザクションを開始し、
    正常終了時に自動コミット、例外発生時に自動ロールバックを行います。
    FastAPI の Depends() などで使用できます。

    Yields:
        Session: トランザクション管理されたセッション

    Raises:
        Exception: セッション内で発生した例外を再送出します

    Example:
        >>> # FastAPI での使用例
        >>> @router.post("/items")
        >>> async def create_item(
        >>>     item_data: ItemCreate,
        >>>     session: Session = Depends(get_db_transaction)
        >>> ):
        >>>     item = Item(**item_data.dict())
        >>>     session.add(item)
        >>>     # 自動的にコミットされます
        >>>     return item
    """
    session = SessionLocal()
    try:
        with session.begin():
            yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def transaction() -> Generator[Session, None, None]:
    """
    トランザクション管理用のコンテキストマネージャーです。

    CLI スクリプトや通常の Python コードで使用するための with 文対応のヘルパーです。
    正常終了時に自動コミット、例外発生時に自動ロールバックを行います。

    Yields:
        Session: トランザクション管理されたセッション

    Raises:
        Exception: セッション内で発生した例外を再送出します

    Example:
        >>> # CLI スクリプトでの使用例
        >>> with transaction() as session:
        >>>     item = Item(name="example")
        >>>     session.add(item)
        >>>     # with ブロック終了時に自動コミットされます
    """
    session = SessionLocal()
    try:
        with session.begin():
            yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """
    新しいセッションインスタンスを直接取得します。

    トランザクション管理は行わないため、明示的に commit() や close() を呼ぶ必要があります。
    低レベルな制御が必要な場合に使用します。

    Returns:
        Session: 新しい SQLAlchemy セッション

    Note:
        このセッションは使用後に必ず close() を呼び出してください。

    Example:
        >>> # 明示的なセッション管理が必要な場合
        >>> session = get_session()
        >>> try:
        >>>     item = Item(name="example")
        >>>     session.add(item)
        >>>     session.commit()
        >>> except Exception:
        >>>     session.rollback()
        >>>     raise
        >>> finally:
        >>>     session.close()
    """
    return SessionLocal()


__all__ = [
    'get_db_session',
    'get_db_transaction',
    'transaction',
    'get_session',
]
