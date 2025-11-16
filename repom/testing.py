"""
Testing utilities for repom-based projects.

このモジュールは、repom を使用する外部プロジェクト（mine-py など）が
簡単に高速なテストインフラを構築できるようにヘルパー関数を提供します。

主な機能:
- Transaction Rollback パターンによる高速テスト
- pytest フィクスチャの簡単な作成
- DB 作成回数の最小化（セッションスコープで1回のみ）

使用例:
    ```python
    # external_project/tests/conftest.py
    import pytest
    from repom.testing import create_test_fixtures

    db_engine, db_test = create_test_fixtures()
    ```
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from typing import Callable, Optional
from repom.db import Base
from repom.config import config, load_set_model_hook_function


def create_test_fixtures(
    db_url: Optional[str] = None,
    model_loader: Optional[Callable[[], None]] = None
):
    """
    Transaction Rollback パターンを使用したテストフィクスチャを作成

    この関数は、pytest フィクスチャとして使用できる2つの関数を返します：
    - db_engine: セッションスコープ（全テストで1回だけDB作成）
    - db_test: 関数スコープ（各テストで独立したトランザクション）

    Parameters
    ----------
    db_url : str, optional
        データベース接続URL。指定しない場合は config.db_url を使用
    model_loader : Callable, optional
        モデルロード関数。指定しない場合は load_set_model_hook_function を使用

    Returns
    -------
    tuple[Callable, Callable]
        (db_engine フィクスチャ, db_test フィクスチャ) のタプル

    Examples
    --------
    基本的な使用方法::

        # tests/conftest.py
        import pytest
        from repom.testing import create_test_fixtures

        db_engine, db_test = create_test_fixtures()

    カスタムDB URLを指定::

        db_engine, db_test = create_test_fixtures(
            db_url="sqlite:///:memory:"
        )

    カスタムモデルローダーを指定::

        def load_my_models():
            from my_project import models  # モデルをインポート

        db_engine, db_test = create_test_fixtures(
            model_loader=load_my_models
        )

    Notes
    -----
    この関数が返すフィクスチャは以下の特徴を持ちます：

    - **高速**: DB作成は1回のみ、各テストはトランザクションロールバックのみ
    - **分離**: 各テストは独立したトランザクション内で実行
    - **クリーン**: 自動ロールバックで確実にリセット
    - **安全**: 例外発生時もトランザクション状態を正しく処理
    """
    # デフォルト値の設定
    _db_url = db_url or config.db_url
    _model_loader = model_loader or load_set_model_hook_function

    @pytest.fixture(scope='session')
    def db_engine():
        """
        セッション全体で共有されるデータベースエンジン

        - テストセッション開始時に1回だけDB作成
        - 全テスト終了後にクリーンアップ
        - エンジンとコネクションプールを共有することで高速化
        """
        # モデルをロード
        _model_loader()

        # エンジン作成
        engine = create_engine(_db_url)

        # テーブル作成（1回のみ）
        Base.metadata.create_all(bind=engine)

        yield engine

        # クリーンアップ
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    @pytest.fixture()
    def db_test(db_engine):
        """
        各テスト関数で独立したトランザクション環境を提供

        トランザクションロールバック方式により：
        - ✅ 高速（DB再作成不要、ロールバックのみ）
        - ✅ 完全な分離（各テストが独立したトランザクション内）
        - ✅ クリーンな状態（自動ロールバックで確実にリセット）

        動作の流れ:
        1. テスト開始: 新しいコネクションとトランザクション開始
        2. テスト実行: 独立したトランザクション内でデータ操作
        3. テスト終了: ロールバック → すべての変更が取り消される
        """
        # 新しいコネクションとトランザクション開始
        connection = db_engine.connect()
        transaction = connection.begin()

        # トランザクション内のセッション作成
        session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=connection)
        )

        yield session

        # クリーンアップ（確実にロールバック）
        session.close()
        # トランザクションがまだアクティブな場合のみロールバック
        if transaction.is_active:
            transaction.rollback()
        connection.close()

    return db_engine, db_test
