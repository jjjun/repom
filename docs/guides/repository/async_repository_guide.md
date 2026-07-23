# AsyncBaseRepository ガイド

`AsyncBaseRepository` は `BaseRepository` と同じ query、bulk、Soft Delete API を
`AsyncSession` 向けに提供します。I/O メソッドはすべて `await` してください。

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

読み取りだけなら `get_async_db_session()`、複数の書き込みを1トランザクションに
まとめるなら `get_async_db_transaction()` を dependency として使います。
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
    session: AsyncSession = Depends(get_async_db_transaction),
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
`get_async_db_transaction()` を `async for` で利用し、終了時に
`dispose_engines()` を呼びます。

## 主要 API

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

`options` と `default_options` には `selectinload()` や `joinedload()` を指定できます。
非同期 ORM では暗黙の lazy load を避け、必要な relationship を明示的に
eager load してください。

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

## Soft Delete

`SoftDeletableMixin` を持つモデルでは `soft_delete()`、`restore()`、
`permanent_delete()`、`find_deleted()` を await できます。現行の Repository
Soft Delete メソッドは自身で commit するため、より大きな外部 transaction に
まとめたい場合はモデルの `soft_delete()` / `restore()` を呼び、呼び出し側の
session で flush / commit してください。

詳細は [Soft Delete ガイド](../model/soft_delete_guide.md)を参照してください。

## 関連資料

- [BaseRepository 基礎](base_repository_guide.md)
- [検索と eager loading](repository_advanced_guide.md)
- [セッション管理](repository_session_patterns.md)
- [`AsyncBaseRepository` 実装](../../../repom/repositories/async_base_repository.py)
