# fmt: off
import hashlib
import os
import shutil
import sys
import pytest
import pytest_asyncio
import logging
from pathlib import Path
from tempfile import mkdtemp

from dotenv import load_dotenv


load_dotenv()

_TEST_SESSION_ROOT = mkdtemp(prefix='repom-tests-')
_ORIGINAL_CONFIG_HOOK = os.environ.get('CONFIG_HOOK')
if _ORIGINAL_CONFIG_HOOK and _ORIGINAL_CONFIG_HOOK.strip():
    os.environ['REPOM_TEST_ORIGINAL_CONFIG_HOOK'] = _ORIGINAL_CONFIG_HOOK
elif 'REPOM_TEST_ORIGINAL_CONFIG_HOOK' in os.environ:
    del os.environ['REPOM_TEST_ORIGINAL_CONFIG_HOOK']

os.environ['REPOM_TEST_ROOT'] = _TEST_SESSION_ROOT
os.environ['CONFIG_HOOK'] = 'tests.session_config:hook_config'


def _snapshot_protected_paths():
    """Capture repository data and migration files that tests must not change."""
    repo_root = Path(__file__).resolve().parents[1]
    protected_roots = (
        repo_root / 'data',
        repo_root / 'data_master',
        repo_root / 'alembic' / 'versions',
    )
    snapshot = {}

    for root in protected_roots:
        if not root.exists():
            continue

        paths = (root, *root.rglob('*'))
        for path in paths:
            relative_path = path.relative_to(repo_root)
            file_stat = path.lstat()
            entry = {
                'mode': file_stat.st_mode,
                'mtime_ns': file_stat.st_mtime_ns,
                'size': file_stat.st_size,
            }
            if path.is_symlink():
                entry['target'] = os.readlink(path)
            elif path.is_file():
                entry['content_hash'] = hashlib.sha256(path.read_bytes()).digest()
            snapshot[relative_path] = entry

    return snapshot


_PROTECTED_PATHS_AT_IMPORT = _snapshot_protected_paths()

os.environ['EXEC_ENV'] = 'test'

from repom.testing import create_test_fixtures, create_async_test_fixtures  # noqa: E402

# テストモデルをインポート（自動登録される）


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_SESSION_ROOT, ignore_errors=True)


def _debug_logging_enabled(config):
    """Return whether explicit verbose output should enable DEBUG logging."""
    # pyproject.toml adds -q, so an explicit -vv produces effective verbosity 1.
    return config.option.verbose >= 1


def pytest_configure(config):
    # Windows 環境で絵文字を含む出力が cp932 エンコードエラーを起こさないよう UTF-8 に統一
    # （--capture=tee-sys と capsys の teardown 連携で発生する UnicodeEncodeError を防止）
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    # -vv オプション時のみデバッグログを有効化
    if _debug_logging_enabled(config):
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        logging.getLogger('repom').setLevel(logging.DEBUG)
    else:
        # 通常のテスト実行時は WARNING レベル以上のみ
        logging.getLogger('repom').setLevel(logging.WARNING)

    # 外部ライブラリの詳細ログを抑制（常に WARNING 以上）
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


@pytest.fixture(scope='session', autouse=True)
def setup_database_tables(protect_repository_data, redirect_test_logs):
    """
    データベースタイプに応じてテーブルを自動作成

    config.db_type に基づいて適切なセットアップを実行:
    - SQLite: 同期・非同期両方のengineにテーブル作成
    - PostgreSQL: 同期engineのみにテーブル作成

    autouse=True により、全テストで自動実行されます。
    """
    from repom.models.base_model import Base
    from repom.database import get_sync_engine, get_async_engine
    from repom.config import config
    from repom.utility import load_models
    import asyncio

    # モデルをロード（テーブル定義を Base.metadata に登録）
    load_models()

    # 同期 engine にテーブル作成
    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)

    # SQLite の場合のみ非同期 engine にもテーブル作成
    if config.db_type == 'sqlite':
        async def create_async_tables():
            async_engine = await get_async_engine()
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(create_async_tables())

    yield

    # SQLite の場合のみクリーンアップ（PostgreSQL はデータ永続化）
    if config.db_type == 'sqlite':
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope='session', autouse=True)
def setup_test_models(protect_repository_data, redirect_test_logs, db_engine):
    """テストモデルのテーブルを作成

    このフィクスチャは session スコープで自動実行され、
    tests/fixtures/models/ で定義されたモデルのテーブルを作成します。

    Transaction Rollback パターンと組み合わせることで:
    - テーブル作成は1回のみ（高速）
    - 各テストはトランザクションで分離
    - データは自動ロールバック

    Note: db_engine フィクスチャに依存しているため、
    db_engine の作成後に実行されます。
    """
    from repom.models.base_model import BaseModel

    # BaseModel.metadata には repom のモデル + テストモデルが含まれる
    BaseModel.metadata.create_all(bind=db_engine)
    yield
    # テスト終了後のクリーンアップ（セッション終了時）
    # Transaction Rollback パターンでは通常不要だが、念のため実行
    BaseModel.metadata.drop_all(bind=db_engine)


# repom/testing.py のヘルパー関数を使用してフィクスチャを作成
# 同期版（既存）
db_engine, db_test = create_test_fixtures()

# async 版（新規）
async_db_engine, async_db_test = create_async_test_fixtures()


@pytest_asyncio.fixture(params=('sync', 'async'))
async def repository_adapter(request, db_test, async_db_test):
    """Run shared repository tests against sync and async implementations."""
    from inspect import isawaitable
    from repom.repositories import AsyncBaseRepository, BaseRepository

    class RepositoryAdapter:
        def __init__(self, mode, session):
            self.mode = mode
            self.session = session
            self.repository_class = (
                BaseRepository if mode == 'sync' else AsyncBaseRepository
            )

        async def call(self, method, *args, **kwargs):
            result = method(*args, **kwargs)
            if isawaitable(result):
                return await result
            return result

    session = db_test if request.param == 'sync' else async_db_test
    return RepositoryAdapter(request.param, session)


@pytest_asyncio.fixture
async def isolated_async_database_manager(monkeypatch):
    """Provide a fresh application async engine with the mapped tables created."""
    import repom.database as database_module
    from repom.database import Base, DatabaseManager

    manager = DatabaseManager()
    engine = await manager.get_async_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(database_module, '_db_manager', manager)

    yield manager

    await manager.dispose_async()


@pytest.fixture(scope='session', autouse=True)
def protect_repository_data():
    """Fail if the test session modifies local data or migration files."""
    before = _PROTECTED_PATHS_AT_IMPORT
    yield
    after = _snapshot_protected_paths()

    changed_paths = sorted(
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    )
    if changed_paths:
        changed_list = '\n'.join(f'  {path}' for path in changed_paths)
        pytest.fail(
            'Tests changed protected repository data or migrations:\n'
            f'{changed_list}',
            pytrace=False,
        )


@pytest.fixture(scope='session', autouse=True)
def redirect_test_logs(protect_repository_data, tmp_path_factory):
    """Keep default application log handlers outside the repository data tree."""
    from repom.config import config

    logger = logging.getLogger('repom')
    original_handlers = list(logger.handlers)
    test_log_path = tmp_path_factory.mktemp('repom-test-logs')
    config.log_path = str(test_log_path)

    for handler in original_handlers:
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()

    yield

    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()


@pytest.fixture(autouse=True)
def isolate_test_file_logs(tmp_path, monkeypatch):
    """Keep file handlers created by tests inside each test's temporary directory."""
    from repom.config import config

    monkeypatch.setattr(config, 'log_path', str(tmp_path))
    logger = logging.getLogger('repom')
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()

    yield

    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()


# ==================== Test Cleanup ====================
# Pure SQLAlchemy behavior tests use an isolated registry so cleanup does not
# unmap Repom models used by other tests.
