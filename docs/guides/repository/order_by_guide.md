# order_by ガイド

このガイドは、`repom` における `order_by` の標準的な使い方をまとめた資料です。

対象:

- `repom` を利用するアプリケーション
- Repository のソート仕様を OpenAPI に公開したい API 実装

## 基本ルール

`order_by` は canonical form のみを受け付けます。

- `column:asc`
- `column:desc`

```python
# OK
repo.find(order_by="created_at:desc")

# NG（bare column）
repo.find(order_by="created_at")
# -> ValueError
```

## Repository 定義

```python
class TaskRepository(BaseRepository[Task]):
    allowed_order_columns = BaseRepository.allowed_order_columns + ["priority"]
    default_order_by = "created_at:desc"
```

- `allowed_order_columns`: ソート可能なカラムのホワイトリスト
- `default_order_by`: `order_by` 未指定時の既定値（canonical form で指定）

## FastAPI 統合

`build_order_by_query_depends()` を使うと、Repository 定義から OpenAPI enum を生成できます。

```python
from fastapi import Depends
from repom import build_order_by_query_depends

@router.get("/tasks")
def read_tasks(
    order_params: dict = Depends(build_order_by_query_depends(TaskRepository)),
):
    return order_params
```

返却値の形:

```python
{"order_by": "created_at:desc"}
```

## introspection API

候補や既定値はプログラムから参照できます。

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

## virtual_order_columns（応用）

JOIN 先カラムや集計値など、モデル実カラムではない列を OpenAPI に公開したい場合は、
`virtual_order_columns` を使います。

```python
class TaskRepository(BaseRepository[Task]):
    allowed_order_columns = BaseRepository.allowed_order_columns + ["rating"]
    virtual_order_columns = ["rating"]
```

ルール:

- `virtual_order_columns` の列は `allowed_order_columns` にも含める
- `parse_order_by()` は virtual 列に対して `VirtualColumnError` を送出する
- virtual 列の実際のソート式は、リポジトリのカスタムメソッド側で実装する
- `find()` に virtual 列を直接渡す用途は非対応

カスタムメソッドでの実装イメージ:

```python
from sqlalchemy import asc, desc
from repom import VirtualColumnError

def find_with_rating(self, order_by: str = "created_at:desc"):
    try:
        order_expr = self.parse_order_by(Task, order_by)
    except VirtualColumnError as e:
        direction = desc if e.direction == "desc" else asc
        if e.column_name == "rating":
            order_expr = direction(Review.rating)
        else:
            raise

    stmt = select(Task).outerjoin(Review, ...).order_by(order_expr)
    return self.session.execute(stmt).scalars().all()
```

## 運用上の推奨

- `default_order_by` の正本は repository 側に寄せる
- decorator 側・endpoint 側で `default_order_by` を二重管理しない
- OpenAPI 公開値は `build_order_by_query_depends()` に統一する

## 移行メモ（旧仕様から来る場合）

- `order_by="column"` は `column:asc` へ置換する
- repository の `default_order_by` を canonical form に統一する
- endpoint の手書き `order_by` dependency は `build_order_by_query_depends()` へ置換する
