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
repo.find(order_by="created_at:desc", limit=100)

# NG（bare column）
repo.find(order_by="created_at", limit=100)
# -> ValueError
```

## Repository 定義

```python
class TaskRepository(BaseRepository[Task]):
    allowed_order_columns = BaseRepository.allowed_order_columns + ["priority"]
    default_order_by = "created_at:desc"
```

- `allowed_order_columns`: ソート可能なカラムのホワイトリスト
- `default_order_by`: `order_by` 未指定時の既定値。canonical form の文字列、SQLAlchemy 式、
  または式のリスト / タプルを指定できます。SQLAlchemy 式はカラム名のホワイトリストを
  通らないため、アプリケーション側で安全な式だけを指定してください。

`default_order_by` は通常の Python 属性検索順序で解決され、インスタンス属性がクラス属性を
上書きします。`get_order_by_default_value()` は文字列の既定値だけを canonical string として
返し、文字列以外が設定されている場合は `None` を返します。

OpenAPI 用の `order_by` dependency は利用側フレームワーク（fast-domain）が構築します。
repom は並び替え候補を取得する introspection API を提供します。

## 決定的な並び順

`order_by` と `default_order_by` のどちらも指定しない場合、すべての主キー属性の
昇順で並びます。これは `id` 属性を持たないモデルや複合主キーにも適用されます。

`"created_at:desc"` のように文字列で並び順を指定すると、ソート列として既に使われている
ものを除き、主キー属性が同じ方向のキーとして末尾に追加されます。これにより、同じ
ソート値の行も `limit` と `offset` を使う場合を含めて安定した順序になります。たとえば
`"created_at:desc"` は `created_at DESC, id DESC` の順で並び、`"id:desc"` では `id` は
一度だけ指定されます。

SQLAlchemy の並び替え式を `find()` または `set_find_option()` に指定すると、その内容が
完全な並び順になります。式を直接渡した場合、自動で主キーのタイブレーカーは追加されない
ため、ページングに使う場合は必要な一意キーを式に含めてください。複数の式を指定するには、
リストまたはタプルを渡します。

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
