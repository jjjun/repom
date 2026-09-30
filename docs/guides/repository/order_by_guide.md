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

Repository 定義から OpenAPI 用の `order_by` dependency を構築する機能
（旧 `build_order_by_query_depends()`）は利用側フレームワーク（fast-domain）に
移管されました。repom には並び替え候補を取得する introspection API のみが
残ります。

## 決定的な並び順

`order_by` と `default_order_by` のどちらも指定しない場合、すべての主キー属性の
昇順で並びます。これは `id` 属性を持たないモデルや複合主キーにも適用されます。

`"created_at:desc"` のように文字列で並び順を指定すると、ソート列として既に使われている
ものを除き、主キー属性が同じ方向のキーとして末尾に追加されます。これにより、同じ
ソート値の行も `limit` と `offset` を使う場合を含めて安定した順序になります。たとえば
`"created_at:desc"` は `created_at DESC, id DESC` の順で並び、`"id:desc"` では `id` は
一度だけ指定されます。

SQLAlchemy の並び替え式を指定すると、指定した内容が完全な並び順になります。複数の式を
指定するには、リストまたはタプルを渡します。

```python
order_by=[Task.created_at.desc(), Task.id.desc()]
```

`get_by(..., single=True)` は一致した行を主キー属性すべての昇順で並べてから先頭を返し、
`default_order_by`（仮想カラムを指定している場合があります）は適用しません。
`get_by_id()` は主キーの等価条件で最大 1 行に一致するため、並び順を追加しません。

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
from repom import BaseRepository, VirtualColumnError

class TaskRepository(BaseRepository[Task]):
    allowed_order_columns = BaseRepository.allowed_order_columns + ["rating"]
    virtual_order_columns = ["rating"]

    def find_with_rating(self, order_by: str = "created_at:desc"):
        try:
            order_expr = self.parse_order_by(Task, order_by)
        except VirtualColumnError as e:
            direction = desc if e.direction == "desc" else asc
            if e.column_name == "rating":
                order_expr = direction(Review.rating)
            else:
                raise

        filters = []
        self._append_soft_delete_filter(filters)
        stmt = self._base_select().outerjoin(Review, Review.task_id == Task.id)
        if filters:
            stmt = stmt.where(*filters)
        stmt = self.set_find_option(stmt, order_by=order_expr, limit=100)
        return self.session.execute(stmt).scalars().unique().all()
```

このメソッドは `TaskRepository(session=session)` のように外部セッションを明示して使ってください。`_base_select()`、soft-delete filter、`set_find_option()` を使い、通常の検索条件と取得上限を保ちます。

## 運用上の推奨

- `default_order_by` の正本は repository 側に寄せる
- decorator 側・endpoint 側で `default_order_by` を二重管理しない

## 移行メモ（旧仕様から来る場合）

- `order_by="column"` は `column:asc` へ置換する
- repository の `default_order_by` を canonical form に統一する
