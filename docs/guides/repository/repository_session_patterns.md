# Session and transaction patterns

Repository constructors accept an optional SQLAlchemy session:

```python
repo = TaskRepository(session=session)
```

Passing a session makes the caller the transaction owner. Repository write
methods flush changes but do not commit that external session. Without a
session, a repository opens a session for each operation; its write methods
commit and refresh automatically.

Use an explicit transaction whenever several repository operations must
succeed or fail together.

## Synchronous application code

`get_reusable_sync_transaction()` is the usual context manager for workers,
commands, and other long-running processes:

```python
from repom.database import get_reusable_sync_transaction


with get_reusable_sync_transaction() as session:
    task_repo = TaskRepository(session=session)
    audit_repo = AuditRepository(session=session)

    task = task_repo.dict_save({"title": "Review"})
    audit_repo.dict_save({"task_id": task.id, "action": "created"})
```

The context manager commits on success and rolls back on error. It leaves the
engine available for the next transaction in the same process.

For a one-shot script, use `get_standalone_sync_transaction()`. It has the
same transaction semantics and disposes the engine on exit:

```python
from repom.database import get_standalone_sync_transaction


with get_standalone_sync_transaction() as session:
    tasks = TaskRepository(session=session).get_all()
```

## FastAPI dependencies

The sync generator functions are dependency providers, not context managers:

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from repom.database import get_db_session, get_db_transaction


@app.get("/tasks")
def list_tasks(session: Session = Depends(get_db_session)):
    return TaskRepository(session=session).get_all()


@app.post("/tasks")
def create_task(session: Session = Depends(get_db_transaction)):
    return TaskRepository(session=session).dict_save({"title": "Review"})
```

Use `get_db_session()` for a session without an automatic commit and
`get_db_transaction()` when the request should commit on success and roll
back on error.

Do not write `with get_db_session()`: it is a generator intended for
dependency injection.

## Asynchronous application code

Use the async dependency providers with FastAPI and configure repom's lifespan
manager so engines are disposed during shutdown:

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
    session: AsyncSession = Depends(get_async_db_transaction),
):
    return await TaskRepository(session=session).dict_save({"title": "Review"})
```

For a one-shot async script, use the async context manager:

```python
import asyncio

from repom.database import get_standalone_async_transaction


async def main():
    async with get_standalone_async_transaction() as session:
        tasks = await TaskRepository(session=session).get_all()
        print(tasks)


asyncio.run(main())
```

Advanced long-running code can iterate `get_async_db_transaction()` directly,
but it must call `dispose_engines()` when the process is finished. The
standalone context manager is safer for ordinary scripts.

## Ownership rules

- Pass sessions by keyword: `Repository(session=session)`.
- Do not pass a session as the first positional argument; that position is the
  optional model.
- Do not share one `AsyncSession` between concurrently running tasks.
- With an external session, the caller owns commit and rollback.
- Use one explicit transaction for operations that must be atomic.
- Prefer repository subclasses with a declared model over repeating the model
  at each call site.

See [AsyncBaseRepository](async_repository_guide.md) for async-specific query
and save examples.
