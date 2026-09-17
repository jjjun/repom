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
from repom.database import Base, DatabaseManager, safe_db_url
from repom.database import convert_to_async_uri  # noqa: F401 - re-exported, see below
from repom.config import config
from repom.utility import load_models


def _is_in_memory_sqlite_url(db_url: str) -> bool:
    return db_url.startswith("sqlite") and ":memory:" in db_url


def _require_test_database(db_url: str, allow_destructive: bool) -> None:
    """Refuse to proceed unless dropping ``db_url``'s tables at teardown is safe.

    create_test_fixtures / create_async_test_fixtures drop every table in
    Base.metadata when their session-scoped engine fixture tears down. Without
    this guard, a consuming project running pytest with EXEC_ENV unset or
    left at its dev default would create tables in - and then drop - its real
    dev/prod database (repom#135).
    """
    if config.exec_env == "test" or _is_in_memory_sqlite_url(db_url) or allow_destructive:
        return
    raise RuntimeError(
        f"Refusing to create test fixtures against {safe_db_url(db_url)}: "
        f"EXEC_ENV={config.exec_env!r} is not 'test' and this is not an "
        "in-memory SQLite database. Pass allow_destructive=True to target "
        "this database anyway, or set EXEC_ENV=test."
    )


def create_test_fixtures(
    db_url: Optional[str] = None,
    model_loader: Optional[Callable[[], None]] = None,
    allow_destructive: bool = False
):
    """
    Transaction Rollback パターンを使用したテストフィクスチャを作成

    この関数は、pytest フィクスチャとして使用できる2つの関数を返します：
    - db_engine: セッションスコープ（全テストで1回だけDB作成）
    - db_test: 関数スコープ（各テストで独立したトランザクション）

    Parameters
    ----------
    db_url : str, optional
        データベース接続URL。指定しない場合は in-memory SQLite（sqlite:///:memory:）を使用
    model_loader : Callable, optional
        モデルロード関数。指定しない場合は load_models を使用
    allow_destructive : bool, optional
        EXEC_ENV が test でなく、かつ in-memory SQLite でもない db_url を明示的に
        許可する。既定は False で、その場合は RuntimeError を送出する
        （リアルな dev/prod データベースを誤って drop_all しないための安全策、
        repom#135）

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
    _db_url = db_url if db_url is not None else "sqlite:///:memory:"
    _require_test_database(_db_url, allow_destructive)
    _model_loader = model_loader or load_models

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

        # フィクスチャ URL に応じた engine_kwargs を導出（config.db_type ではなく
        # _db_url 自体のドライバーで判定するため、config の db_type と異なる URL
        # を渡しても正しい設定になる）
        kwargs = config.engine_kwargs_for_url(_db_url)

        engine = create_engine(_db_url, **kwargs)

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
            # The inherited False default is documented in the repository guide.
            sessionmaker(autocommit=False, autoflush=config.autoflush, bind=connection)
        )

        yield session

        # クリーンアップ（確実にロールバック）
        session.close()
        # トランザクションがまだアクティブな場合のみロールバック
        if transaction.is_active:
            transaction.rollback()
        connection.close()

    return db_engine, db_test


# ========================================
# Async Support (SQLAlchemy 2.0+)
# ========================================

# convert_to_async_uri は repom.database.convert_to_async_uri のエイリアス
# （DatabaseManager._convert_to_async_uri に実装を一本化: repom#166）。
# 上の import 文により repom.testing.convert_to_async_uri としても import 可能。


def create_async_test_fixtures(
    db_url: Optional[str] = None,
    model_loader: Optional[Callable[[], None]] = None,
    allow_destructive: bool = False
):
    """
    async Transaction Rollback パターンを使用したテストフィクスチャを作成

    FastAPI Users など async ライブラリのテストに使用します。
    既存の create_test_fixtures() と同じパターンで async 対応。

    Parameters
    ----------
    db_url : str, optional
        データベース接続URL。指定しない場合は in-memory SQLite（sqlite:///:memory:）を使用
    model_loader : Callable, optional
        モデルロード関数。指定しない場合は load_models を使用
    allow_destructive : bool, optional
        create_test_fixtures と同じ安全策（repom#135）。既定は False

    Returns
    -------
    tuple[Callable, Callable]
        (async_db_engine フィクスチャ, async_db_test フィクスチャ) のタプル

    Examples
    --------
    基本的な使用方法::

        # tests/conftest.py
        import pytest
        from repom.testing import create_async_test_fixtures

        async_db_engine, async_db_test = create_async_test_fixtures()

    テストでの使用::

        @pytest.mark.asyncio
        async def test_create_user(async_db_test):
            from sqlalchemy import select

            user = User(name="test")
            async_db_test.add(user)
            await async_db_test.flush()

            stmt = select(User).where(User.name == "test")
            result = await async_db_test.execute(stmt)
            found = result.scalar_one_or_none()

            assert found is not None

    Notes
    -----
    必要な依存関係::

        # pyproject.toml
        [project]
        dependencies = ["repom[async-all]"]  # SQLite のみなら repom[async] で可

        [dependency-groups]
        dev = ["pytest-asyncio>=0.23.0,<1.0.0"]

    async では lazy loading が使えません::

        # ❌ lazy loading は動作しない
        user.posts  # AttributeError

        # ✅ eager loading を使用
        from sqlalchemy.orm import selectinload

        stmt = select(User).options(selectinload(User.posts))
        result = await session.execute(stmt)
        user = result.scalar_one()
        user.posts  # OK
    """
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        import pytest_asyncio
    except ImportError as e:
        raise ImportError(
            "Async support requires additional dependencies. "
            "Install with: uv add \"repom[async-all]\" pytest-asyncio"
        ) from e

    # デフォルト値の設定
    _db_url = db_url if db_url is not None else "sqlite:///:memory:"
    _require_test_database(_db_url, allow_destructive)
    _model_loader = model_loader or load_models

    @pytest_asyncio.fixture(scope='session')
    async def async_db_engine():
        """
        セッション全体で共有される async データベースエンジン

        - テストセッション開始時に1回だけDB作成
        - 全テスト終了後にクリーンアップ
        - async engine とコネクションプールを共有することで高速化
        """
        # モデルをロード
        _model_loader()

        # フィクスチャ URL に応じた engine_kwargs を導出し、async ドライバー用の
        # URL・connect_args に変換する（DatabaseManager.get_async_engine と
        # 同じ resolve_engine_settings を使うことで実装の分岐を防ぐ）
        base_kwargs = config.engine_kwargs_for_url(_db_url)
        _, (async_url, kwargs) = DatabaseManager.resolve_engine_settings(_db_url, base_kwargs)

        engine = create_async_engine(async_url, **kwargs)

        # テーブル作成（async での create_all）
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        # クリーンアップ
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    @pytest_asyncio.fixture
    async def async_db_test(async_db_engine):
        """
        各テスト関数で独立した async トランザクション環境を提供

        トランザクションロールバック方式により：
        - ✅ 高速（DB再作成不要、ロールバックのみ）
        - ✅ 完全な分離（各テストが独立したトランザクション内）
        - ✅ クリーンな状態（自動ロールバックで確実にリセット）

        動作の流れ:
        1. テスト開始: 新しい async connection と transaction 開始
        2. テスト実行: 独立したトランザクション内でデータ操作
        3. テスト終了: ロールバック → すべての変更が取り消される
        """
        # 新しい async connection とトランザクション開始
        connection = await async_db_engine.connect()
        transaction = await connection.begin()

        # トランザクション内の async session 作成
        AsyncSessionLocal = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=config.autoflush,
        )

        session = AsyncSessionLocal()

        yield session

        # クリーンアップ（確実にロールバック）
        await session.close()
        if transaction.is_active:
            await transaction.rollback()
        await connection.close()

    return async_db_engine, async_db_test
