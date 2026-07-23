# Testing Guide

repom は pytest 用の同期・非同期 fixture factory を提供します。DB schema は
test session ごとに作成し、各 test は独立した transaction を rollback するため、
テスト間でデータを残しません。

## このリポジトリでの実行

```bash
uv run pytest
uv run pytest tests/unit_tests
uv run pytest tests/behavior_tests
uv run pytest tests/integration_tests
uv run pytest -vv -s
```

既定の pytest 設定は `pyproject.toml` の `[tool.pytest.ini_options]` にあります。
通常実行は成功時の出力を抑え、`-vv -s` の明示時だけ詳細な stdout と DEBUG log を
有効にします。

## 同期 fixture

外部プロジェクトの `tests/conftest.py` では次の2 fixture を定義できます。

```python
from repom.testing import create_test_fixtures

db_engine, db_test = create_test_fixtures()
```

- `db_engine`: session scope の SQLAlchemy Engine
- `db_test`: function scope の Session

`db_test` は rollback 対象の外部 session です。Repository に明示して使います。

```python
from repom import BaseRepository


def test_save_task(db_test):
    repo = BaseRepository(Task, session=db_test)
    task = repo.save(Task(title="test"))

    assert task.id is not None
    assert repo.get_by_id(task.id) is task
```

テスト中に `db_test.commit()` を呼ぶ必要はありません。fixture の transaction
境界を保つため、通常は `flush()` または Repository の `save()` を使います。

## 非同期 fixture

```python
from repom.testing import create_async_test_fixtures

async_db_engine, async_db_test = create_async_test_fixtures()
```

```python
import pytest

from repom import AsyncBaseRepository


@pytest.mark.asyncio
async def test_async_save(async_db_test):
    repo = AsyncBaseRepository(Task, session=async_db_test)
    task = await repo.save(Task(title="async test"))

    assert await repo.get_by_id(task.id) is task
```

SQLite async テストには `aiosqlite`、pytest には `pytest-asyncio` が必要です。
このリポジトリの dev dependency には両方が含まれています。

## DB URL とモデル読み込み

factory の引数は同期・非同期で共通です。

```python
db_engine, db_test = create_test_fixtures(
    db_url="sqlite:///:memory:",
    model_loader=load_test_models,
)
```

- `db_url` 未指定時は `config.db_url` を使う。
- `model_loader` 未指定時は `repom.utility.load_models()` を使う。
- `load_models()` は `config.model_locations` を読み、全 import 後に mapper を構成する。

テスト設定は repom module の import 前に確定させてください。このリポジトリの
`tests/conftest.py` は先頭で `EXEC_ENV=test` を設定しています。外部プロジェクトで
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
