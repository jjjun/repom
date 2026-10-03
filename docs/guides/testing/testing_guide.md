# テストガイド

repom は pytest 用の同期・非同期 fixture factory を提供します。DB schema は
test session ごとに作成され、`db_test` / `async_db_test` を通した各 test の書き込みは
test ごとに rollback されます。別 session や別 connection からの書き込みが、この rollback に含まれる保証はありません。

## このリポジトリでの実行

```bash
uv run pytest
uv run pytest tests/unit_tests
uv run pytest tests/behavior_tests
uv run pytest tests/integration_tests
uv run pytest -vv -s
```

PostgreSQL 統合テストは、`CONFIG_HOOK=repom.config_hook:hook_config`、
`EXEC_ENV=test`、`DB_TYPE=postgres`、`POSTGRES_PASSWORD` が設定され、
`127.0.0.1:5433` で PostgreSQL に接続できる場合に実行されます。CI workflow と
`AGENTS.md` に記載されたコマンドは PostgreSQL 統合テスト用にこれらを設定します。
PostgreSQL 統合テストには専用の破棄可能な database を使ってください。テストは固定名の
`integration_test` table を作成・削除するほか、UUID 名の schema も使います。`EXEC_ENV=test` は
database が破棄可能かどうかを検証しません。

この repository の test setup は一時 root を設定し、設定済みの元の config hook も呼び出します。
hook や環境変数から指定した database URL と SQLite path は一時 root の外を指す場合があります。
`tests/conftest.py` の保護対象 path の比較は test session 終了後に変更を検出しますが、root 外への書き込みを
防ぐものではありません。`EXEC_ENV=test` も sandbox ではないため、実行前に接続先を確認してください。

既定の pytest 設定は `pyproject.toml` の `[tool.pytest.ini_options]` にあります。
通常実行は成功時の出力を抑え、`-vv -s` の明示時だけ詳細な stdout と DEBUG log を
有効にします。既定の `addopts` は `-q` と `--benchmark-skip` です。`-q` が通常出力を
抑えるため、詳細を確認するときは `-vv` を指定します。

## 同期 fixture

外部プロジェクトの `tests/conftest.py` では次の2 fixture を定義できます。

```python
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

- `db_engine`: session scope の SQLAlchemy Engine
- `db_test`: function scope の `scoped_session`

`db_test` は rollback 対象の外部 `scoped_session` です。Repository に明示して使います。

`bind_global_manager=True` は fixture engine を `DatabaseManager` に一時的に bind します。
同期 factory は同期 engine だけを、非同期 factory は非同期 engine だけを bind し、反対側の engine は変わりません。
これは engine routing の設定であり、manager API が返す session を `db_test` / `async_db_test` の
session や transaction に参加させるものではありません。in-memory SQLite の `StaticPool` のように pool が
DBAPI connection を共有する場合、fixture session の未 commit 行が見えることはありますが、fixture の rollback は
manager session からの書き込みを取り消す保証をしません。rollback を必要とする書き込みには、fixture の session を
明示して使ってください。fixture 終了時には以前の engine と session factory が復元されます。

`get_standalone_sync_transaction()` と `get_standalone_async_transaction()` は終了時に対応する manager engine を
dispose して cached slot を消去します。global manager の binding 中にこれらを使うと fixture engine を dispose し、
次の manager 呼び出しで設定から別の engine が作成されることがあるため、併用しないでください。
session 管理パターンは[セッション管理ガイド](../repository/repository_session_patterns.md)を
参照してください。

```python
from tests.fixtures.models import User
from repom import BaseRepository


def test_save_user(db_test):
    repo = BaseRepository(User, session=db_test)
    user = repo.save(User(name="Test", email="test@example.com"))

    assert user.id is not None
    assert repo.get_by_id(user.id) is user
```

テスト中に `db_test.commit()` を呼ぶ必要はありません。fixture の transaction
境界を保つため、通常は `flush()` または Repository の `save()` を使います。

## 非同期 fixture

```python
from repom.testing import create_async_test_fixtures

async_db_engine, async_db_test = create_async_test_fixtures()
```

非同期用ファクトリーにも `bind_global_manager=True` を指定できます。manager の非同期 engine だけが
一時的に fixture engine に bind されます。`async_db_test` 以外の session による書き込みが fixture rollback に
含まれる保証はないため、rollback を必要とするコードには `async_db_test` を明示して渡してください。

```python
import pytest

from repom import AsyncBaseRepository
from tests.fixtures.models import User


@pytest.mark.asyncio
async def test_async_save(async_db_test):
    repo = AsyncBaseRepository(User, session=async_db_test)
    user = await repo.save(User(name="Async test", email="async@example.com"))

    assert await repo.get_by_id(user.id) is user
```

SQLite async テストには `aiosqlite`、pytest には `pytest-asyncio` が必要です。
このリポジトリの dev dependency には両方が含まれています。

`repom.testing` は `repom.database.convert_to_async_uri` も再 export します。

## DB URL とモデル読み込み

factory の引数は同期・非同期で共通です。

```python
from tests.fixtures.models import User
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures(
    db_url="sqlite:///:memory:",
)
```

- `db_url` 未指定時は in-memory SQLite（`sqlite:///:memory:`）を使う。正規化後の `EXEC_ENV` が
  `test` でなく、かつ in-memory SQLite でもない `db_url` を渡すと、テスト終了時の
  `drop_all` が実データベースを壊さないよう `RuntimeError` を送出する。実際にその
  データベースへ向けたい場合は `allow_destructive=True` を明示する。
- `model_loader` 未指定時は `repom.utility.load_models()` を使う。
- `load_models()` は `config.model_locations` を読み、全 import 後に mapper を構成する。

テスト設定は repom module の import 前に確定させてください。このリポジトリの
`tests/conftest.py` は repom を import する前に `EXEC_ENV=test` を設定しています。外部プロジェクトで
環境設定の import 順に依存したくない場合は、fixture factory に `db_url` と
`model_loader` を明示します。

汎用 discovery API は `basekit.discovery` が所有します。repom 固有のモデル読み込み
については [モデル自動 import ガイド](../features/auto_import_models_guide.md)を
参照してください。

## モデルの選び方

通常のテストでは、module scope で安定して import できる fixture model を用意します。
このリポジトリでは `tests/fixtures/models/` が正本です。

テスト関数内で declarative model を動的定義すると mapper と metadata が process に
残ります。import 順や mapper 構成自体を検証するテストだけに限定し、既存テストの
cleanup pattern に従ってください。

## transaction の注意

- 1 test につき1つの `db_test` / `async_db_test` を使う。
- 別 session や module-global engine を混在させない。
- `:memory:` SQLite は `StaticPool` で connection を共有する。実 DB 固有の分離、
  locking、dialect 動作は PostgreSQL integration test で確認する。
- async relationship は lazy load に頼らず、`selectinload()` などを指定する。

## fixture 自体を学ぶ

pytest の fixture scope、factory、parametrize の一般的な説明は
[Fixture Guide](fixture_guide.md)を参照してください。実装の正本は
[`repom/testing.py`](../../../repom/testing.py) と
[`tests/conftest.py`](../../../tests/conftest.py) です。
