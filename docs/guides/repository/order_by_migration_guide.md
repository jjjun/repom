# order_by 移行ガイド

このガイドは、Issue #051 に伴う `order_by` 仕様変更を既存利用側から移行するための資料です。

対象:

- `repom` を利用するアプリケーション
- 特に `fast-domain` の endpoint / decorator / dependency 実装

## 変更概要

`order_by` は canonical form のみを正式仕様とします。

新仕様:

- `column:asc`
- `column:desc`

廃止した曖昧仕様:

- `column`

例:

```python
# 旧
repo.find(order_by="created_at")

# 新
repo.find(order_by="created_at:asc")
```

## 何が変わったか

### 1. bare column を受け付けない

`parse_order_by()` は `column` 単独指定を受け付けません。

```python
repo.find(order_by="created_at")
# ValueError
```

### 2. OpenAPI 用 helper を `repom` が提供する

Repository から OpenAPI に公開可能な `order_by` 候補を導出し、FastAPI dependency を生成できます。

```python
from fastapi import Depends
from repom import build_order_by_query_depends

order_params: dict = Depends(build_order_by_query_depends(TaskRepository))
```

返却値は既存に合わせて以下です。

```python
{"order_by": "created_at:desc"}
```

### 3. OpenAPI に出る候補は canonical form のみ

OpenAPI enum には以下のみ出ます。

- `id:asc`
- `id:desc`
- `created_at:asc`
- `created_at:desc`

`id` や `created_at` 単独は出ません。

## fast-domain での移行

### Before

```python
from fast_domain.dependencies import order_by_params

@router.get("/tasks")
def read_tasks(
    order_params: dict = Depends(order_by_params),
):
    ...
```

### After

```python
from repom import build_order_by_query_depends

@router.get("/tasks")
def read_tasks(
    order_params: dict = Depends(build_order_by_query_depends(TaskRepository)),
):
    ...
```

## 置換ポイント

### A. 共通 dependency

置換対象:

- `fast_domain.dependencies.order_by_params`

置換先:

- `build_order_by_query_depends(RepositoryClass)`

Repository が確定していない共通コードでは、旧 dependency を fallback として残してもよいですが、Repository が分かる endpoint では新 helper を優先してください。

### B. endpoint / client から渡す値

置換前:

- `?order_by=created_at`

置換後:

- `?order_by=created_at:asc`

### C. repository 定義

置換前:

```python
class TaskRepository(BaseRepository[Task]):
    default_order_by = "created_at"
```

置換後:

```python
class TaskRepository(BaseRepository[Task]):
    default_order_by = "created_at:asc"
```

## default_order_by の整理方針

`fast-domain` では decorator 側の `default_order_by` と repository 側の `default_order_by` が二重管理になりやすいため、今後は repository 側を正本に寄せることを推奨します。

推奨:

```python
class TaskRepository(BaseRepository[Task]):
    default_order_by = "created_at:desc"
```

```python
@list_endpoint(TaskRepository)
def read_tasks(...):
    ...
```

非推奨:

```python
class TaskRepository(BaseRepository[Task]):
    default_order_by = None

@list_endpoint(TaskRepository, default_order_by="created_at:desc")
def read_tasks(...):
    ...
```

## 利用可能な introspection API

OpenAPI helper 以外にも、候補一覧を直接取得できます。

```python
from repom import (
    get_order_by_columns,
    get_order_by_default_value,
    get_order_by_values,
)

get_order_by_columns(TaskRepository)
get_order_by_values(TaskRepository)
get_order_by_default_value(TaskRepository)
```

## 確認チェックリスト

- [ ] `order_by="column"` を使っている箇所を `column:asc` へ置換した
- [ ] repository の `default_order_by` を canonical form に統一した
- [ ] FastAPI endpoint を `build_order_by_query_depends()` に置換した
- [ ] OpenAPI schema に enum 候補が出ることを確認した
