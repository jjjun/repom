# Repository のセッションとトランザクション管理

Repository のコンストラクタには、任意で SQLAlchemy session を渡せます。

```python
repo = TaskRepository(session=session)
```

session を渡すと、呼び出し側がトランザクションを管理します。Repository の書き込み
メソッドは変更を flush しますが、渡された session を commit しません。session を渡さない
場合、Repository は操作ごとに session を開き、書き込みメソッドが commit と refresh を
自動で行います。

複数の Repository 操作をまとめて成功または失敗させる場合は、明示的なトランザクションを
使ってください。

## 同期アプリケーションコード

読み取りや commit の境界を呼び出し側が管理する場合は
`get_reusable_sync_session()` を使います。

```python
from repom.database import get_reusable_sync_session


with get_reusable_sync_session() as session:
    task_repo = TaskRepository(session=session)
    task = task_repo.get_by_id(1)
    session.commit()  # Optional; the context manager never commits for you.
```

トランザクションが開いたままの場合、終了時に rollback してから session を閉じます。
複数の操作をまとめて commit または rollback する場合は、
`get_reusable_sync_transaction()` を使ってください。

`get_reusable_sync_transaction()` は worker、コマンド、その他の長時間実行プロセスで
一般的に使う context manager です。

```python
from repom.database import get_reusable_sync_transaction


with get_reusable_sync_transaction() as session:
    task_repo = TaskRepository(session=session)
    audit_repo = AuditRepository(session=session)

    task = task_repo.dict_save({"title": "Review"})
    audit_repo.dict_save({"task_id": task.id, "action": "created"})
```

成功時に commit し、エラー時に rollback します。同じプロセスで次のトランザクションを
開始できるよう、engine は破棄しません。

1 回だけ実行するスクリプトでは `get_standalone_sync_transaction()` を使います。
トランザクションの動作は同じですが、終了時に engine を破棄します。

```python
from repom.database import get_standalone_sync_transaction


with get_standalone_sync_transaction() as session:
    tasks = TaskRepository(session=session).get_all()
```

## FastAPI の dependency

同期 generator 関数は dependency provider であり、context manager ではありません。

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from repom.database import get_db_session, get_db_transaction


@app.get("/tasks")
def list_tasks(session: Session = Depends(get_db_session)):
    return TaskRepository(session=session).get_all()


@app.post("/tasks")
def create_task(session: Session = Depends(get_db_transaction, scope="function")):
    return TaskRepository(session=session).dict_save({"title": "Review"})
```

自動 commit しない session には `get_db_session()` を使い、リクエスト成功時に commit、
エラー時に rollback する場合は `get_db_transaction()` を使います。

**FastAPI のトランザクション dependency:** 書き込み route では
`Depends(get_db_transaction, scope="function")` または
`Depends(get_async_db_transaction, scope="function")` を使います。FastAPI >= 0.121.0 が
必要です。既定の `scope="request"` では、response の送信後に commit するため、書き込み
直後に読み込んだ client から変更が見えない場合があります。また commit に失敗しても、
client には成功として通知されます。`scope="function"` では response 送信前に commit
します。送信前に session も閉じるため、streaming 中に session を読み込む
`StreamingResponse` には使わないでください。`get_db_session()` は終了時に commit しない
ため、scope の指定は不要です。`get_async_db_session()` は終了時に commit するので、
読み取り route に使い、その場合は scope の指定は不要です。

`get_db_session()` は dependency injection 用の generator なので、
`with get_db_session()` のようには使わないでください。

## 非同期アプリケーションコード

読み取りや commit の境界を呼び出し側が管理する場合は
`get_reusable_async_session()` を使います。

```python
from repom.database import get_reusable_async_session


async with get_reusable_async_session() as session:
    task_repo = TaskRepository(session=session)
    task = await task_repo.get_by_id(1)
    await session.commit()  # Optional; the context manager never commits for you.
```

終了時に開いたままのトランザクションを rollback し、session を閉じます。この context
manager は commit しません。成功時に commit する FastAPI dependency の
`get_async_db_session()` とは動作が異なります。複数の操作をまとめて commit または
rollback する場合は `get_reusable_async_transaction()` を使ってください。

FastAPI では非同期 dependency provider を使い、repom の lifespan manager を設定して
shutdown 時に engine を破棄します。

```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from repom.database import (
    get_async_db_session,
    get_async_db_transaction,
    get_lifespan_manager,
)

app = FastAPI(lifespan=get_lifespan_manager())


@app.get("/tasks")
async def list_tasks(session: AsyncSession = Depends(get_async_db_session)):
    return await TaskRepository(session=session).get_all()


@app.post("/tasks")
async def create_task(
    session: AsyncSession = Depends(get_async_db_transaction, scope="function"),
):
    return await TaskRepository(session=session).dict_save({"title": "Review"})
```

1 回だけ実行する非同期スクリプトでは、次の async context manager を使います。

```python
import asyncio

from repom.database import get_standalone_async_transaction


async def main():
    async with get_standalone_async_transaction() as session:
        tasks = await TaskRepository(session=session).get_all()
        print(tasks)


asyncio.run(main())
```

長時間実行する非同期コードでは、トランザクションごとに
`get_reusable_async_transaction()` を使い、プロセス終了時に `dispose_engines()` を
呼び出します。

```python
import asyncio

from repom.database import dispose_engines, get_reusable_async_transaction


async def main():
    try:
        async with get_reusable_async_transaction() as session:
            tasks = await TaskRepository(session=session).get_all()
    finally:
        await dispose_engines()


asyncio.run(main())
```

## Repository インスタンスの再利用と並行処理

明示的な `session=` なしで作成した `BaseRepository` または `AsyncBaseRepository` の
インスタンスは、複数の request、task、thread で安全に共有できます。`_session_scope()` は
内部で開いた session を `contextvars.ContextVar` に保持するため、task と thread ごとに
異なる値が使われます。同じインスタンスを同時に呼び出しても、互いの session、未 commit の
行、identity map は共有されません。

明示的な `session=` を渡して作成したインスタンスは、その呼び出し側所有の session に
ライフタイム全体を通して結び付きます。この場合も、1 つの `AsyncSession` を同時実行中の
複数 task で共有しないでください。

## 所有権のルール

- session はキーワード引数で渡します: `Repository(session=session)`。
- session を第 1 位置引数として渡さないでください。この位置は任意の model 用です。
- 1 つの `AsyncSession` を同時実行中の複数 task で共有しないでください。
- 外部 session を使う場合、commit と rollback は呼び出し側が行います。
- 原子的に実行したい操作には、1 つの明示的なトランザクションを使います。
- 呼び出しごとに model を繰り返し指定するより、model を宣言した Repository subclass を
  推奨します。

非同期の検索と保存の例は
[AsyncBaseRepository ガイド](async_repository_guide.md)を参照してください。
