# AsyncBaseRepository ガイド

`AsyncBaseRepository` は `BaseRepository` と同じ query、bulk、Soft Delete API を
`AsyncSession` 向けに提供します。I/O メソッドはすべて `await` してください。
同期版と非同期版の公開 API の対応関係は
[`test_repository_api_parity.py`](../../../tests/unit_tests/test_repository_api_parity.py) で検証されています。
このガイドに記載していない `BaseRepository` の API も `AsyncBaseRepository` で利用できます。

## 定義

型引数からモデルを推論する subclass を推奨します。

```python
from repom import AsyncBaseRepository


class TaskRepository(AsyncBaseRepository[Task]):
    pass
```

一時的な利用ではモデルを明示しても構いません。

```python
repo = AsyncBaseRepository(Task, session=async_session)
```

## FastAPI

読み取りだけなら `Depends(get_async_db_session)`、複数の書き込みを1トランザクションに
まとめるなら `Depends(get_async_db_transaction, scope="function")` を dependency として
使います。`scope="function"` には FastAPI >= 0.121.0 が必要です。デフォルト scope との
違いと `StreamingResponse` の注意は
[セッション管理パターンガイド](repository_session_patterns.md)を参照してください。
`get_async_db_session()` は同期版の `get_db_session()` と異なり、成功時に commit
し、例外発生時は rollback します。
アプリ終了時の engine cleanup には `get_lifespan_manager()` を指定します。

```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from repom.database import (
    get_async_db_transaction,
    get_lifespan_manager,
)

app = FastAPI(lifespan=get_lifespan_manager())


@app.post("/tasks")
async def create_task(
    session: AsyncSession = Depends(get_async_db_transaction, scope="function"),
):
    repo = TaskRepository(session=session)
    task = await repo.save(Task(title="Async task"))
    return task.to_dict()
```

外部セッションを渡した `save()`、`saves()`、bulk API は `flush()` まで行い、
トランザクションの commit / rollback は dependency が担当します。

## CLI とバッチ

FastAPI dependency は async generator です。`async with
get_async_db_session()` のようには使いません。単発スクリプトでは
`get_standalone_async_transaction()` を使います。

```python
from repom.database import get_standalone_async_transaction


async def main():
    async with get_standalone_async_transaction() as session:
        repo = TaskRepository(session=session)
        return await repo.find(limit=20, order_by="created_at:desc")
```

同じプロセスでトランザクションを繰り返す worker は、engine を毎回破棄しない
`get_reusable_async_transaction()` を `async with` で利用し、終了時に
`dispose_engines()` を呼びます。

読み取りや commit の境界を呼び出し側が管理する場合は
`get_reusable_async_session()` を使います。この context manager は commit せず、終了時に
`session.close()` で未完了のトランザクションを破棄します。終了後も読み込み済みのオブジェクト属性は
参照できますが、遅延読み込みはできません。詳細は
[セッション管理パターンガイド](repository_session_patterns.md)を参照してください。

## 主要 API

`find(params=..., filters=...)` は `FilterParams` から生成した条件と `filters` の条件を
AND で結合します。`count()` も `params` と `filters` を受け取ります。
`FilterParams` の定義、`field_to_column` のマッピング、および未マッピングフィールドの
扱いは [FilterParams ガイド](repository_filter_params_guide.md)を参照してください。
未マッピングフィールドの詳細は
[該当する節](repository_filter_params_guide.md#未マッピングフィールド)を参照してください。

```python
task = await repo.get_by_id(1)
tasks = await repo.get_by("status", "active")
one = await repo.get_by("status", "active", single=True)

tasks = await repo.find(
    filters=[Task.status == "active"],
    offset=0,
    limit=20,
    order_by="created_at:desc",
)
count = await repo.count(filters=[Task.status == "active"])
tasks = await repo.find_by_ids([1, 2, 3])

task = await repo.save(Task(title="New"))
created = await repo.bulk_insert([Task(title="A"), Task(title="B")])
updated = await repo.bulk_update([{"id": 1, "status": "done"}])
deleted = await repo.bulk_delete(ids=[1, 2])
```

```python
from repom import AsyncBaseRepository, FilterParams


class TaskParams(FilterParams):
    status: str | None = None


class TaskRepository(AsyncBaseRepository[Task]):
    field_to_column = {"status": Task.status}


repo = TaskRepository()
params = TaskParams(status="active")
tasks = await repo.find(params=params, filters=[Task.priority == "high"], limit=20)
count = await repo.count(params=params, filters=[Task.priority == "high"])
```

`bulk_update()` と `bulk_delete()` は `filters=` を通じて SQLAlchemy 式も受け取ります。
これらの式は、該当する `filter_by=` および `ids=` の条件と AND で結合されます。
`bulk_update()` は既定で論理削除済みの行を対象から除き、含めるには
`include_deleted=True` を指定します。
`bulk_permanent_delete()` は、論理削除対応モデルも含め、常に一致する行を物理削除します。
`get_or_create(lookup, defaults=None)` は `(instance, created)` を返し、一意キーへの同時挿入で
別の処理が先行した場合は、その行を再検索して返します。

```python
updated = await repo.bulk_update([{"status": "expired"}], filters=[Task.created_at < cutoff])
purged = await repo.bulk_permanent_delete(filters=[Task.deleted_at < cutoff])
task, created = await repo.get_or_create({"external_id": external_id}, {"status": "new"})
```

`options` と `default_options` には `selectinload()` や `joinedload()` を指定できます。
非同期 ORM では暗黙の lazy load を避け、必要な relationship を明示的に
eager load してください。コレクション関連への `joinedload()` も指定でき、
結果は `Result.unique()` で重複排除されるため各レコードは1回だけ返ります。

```python
from sqlalchemy.orm import selectinload

task = await repo.get_by_id(
    1,
    options=[selectinload(Task.comments)],
)
```

## 並行実行

1つの `AsyncSession` を複数 task で同時利用しないでください。同じ transaction 内の
query は順番に `await` します。本当に並行実行が必要なら、各 task に独立した
session / transaction を割り当てます。

```python
# 同じ session では逐次実行
tasks = await task_repo.find(limit=10)
users = await user_repo.find(limit=10)
```

`session=` を省略した Repository インスタンスでも、独立して開始された task context では
それぞれ別の内部セッションを使います。一方、内部 session scope が有効な間に開始した
`asyncio.create_task()` や `asyncio.TaskGroup` の子 task は context を引き継ぎ、同じ内部
session object を使うことがあります。`asyncio.gather()` で開始する coroutine も task 化されると
同じ注意が必要です。これらの子 task から同じ Repository を並行して使わないでください。
子 task の書き込みが親 scope の終了前に内部 session を commit する場合もあります。

## Soft Delete

論理削除 API の `soft_delete()`、`restore()`、`permanent_delete()`、`find_deleted()`、
`find_deleted_before()` は await して使います。Repository の Soft Delete メソッドは、
内部セッションなら commit し、外部セッションなら flush のみを行います。外部セッションでは
呼び出し側が transaction を確定します。詳細は
[Soft Delete ガイド](../model/soft_delete_guide.md)を参照してください。

## 関連資料

- [BaseRepository 基礎](base_repository_guide.md)
- [検索と eager loading](repository_advanced_guide.md)
- [セッション管理](repository_session_patterns.md)
- [`AsyncBaseRepository` 実装](../../../repom/repositories/async_base_repository.py)
