# FilterParams ガイド

**目的**: 型安全な検索パラメータを Pydantic モデルとして定義する

**対象読者**: repom を使ってリポジトリ検索を実装する開発者・AI エージェント

**関連ドキュメント**:
- [基礎編：CRUD操作](base_repository_guide.md) - リポジトリの基本的な使い方
- [上級編：検索・フィルタ・options](repository_advanced_guide.md) - 複雑な検索、eager loading、パフォーマンス最適化

FastAPI のクエリ dependency は利用側フレームワーク（fast-domain）の
`as_query_depends()` が提供します。このガイドでは repom の `FilterParams` を
`find(params=...)` と組み合わせて検索する方法を説明します。

---

## 📚 目次

1. [基本的な FilterParams](#基本的な-filterparams)
2. [カスタムリポジトリでの処理](#カスタムリポジトリでの処理)

---

## 基本的な FilterParams

```python
from repom import BaseRepository, FilterParams
from typing import Optional

class TaskFilterParams(FilterParams):
    status: Optional[str] = None
    priority: Optional[str] = None

class TaskRepository(BaseRepository[Task]):
    field_to_column = {
        "status": Task.status,
        "priority": Task.priority,
    }
```

```python
repo = TaskRepository()
tasks = repo.find(params=TaskFilterParams(status="active", priority="high"), limit=100)
```

---

## カスタムリポジトリでの処理

### 方法1: `_build_filters()` をオーバーライド（カスタムロジック）

特殊な比較（日付範囲、OR条件、サブクエリなど）が必要な場合に使用します。

```python
from repom import BaseRepository, FilterParams
from typing import Optional, List

class TaskFilterParams(FilterParams):
    status: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None

class TaskRepository(BaseRepository[Task]):
    def _build_filters(self, params: Optional[TaskFilterParams]) -> list:
        """FilterParams から SQLAlchemy フィルタを構築"""
        if not params:
            return []
        
        filters = []
        
        if params.status:
            filters.append(Task.status == params.status)
        
        if params.priority:
            filters.append(Task.priority == params.priority)
        
        if params.title:
            # 部分一致検索
            filters.append(Task.title.contains(params.title, autoescape=True))
        
        return filters
    
repo = TaskRepository()
params = TaskFilterParams(status="active", priority="high", title="task")
tasks = repo.find(params=params, limit=100)
count = repo.count_by_params(params)
```

### 方法2: `field_to_column` マッピング（シンプル）

等価・部分一致・前方一致・リスト検索・範囲比較だけで済む場合は、マッピングだけで
自動生成できます。

素のカラムを渡した場合は**完全一致（`==`）**になります。リスト型のフィールドは
自動的に `IN` 検索になります。

```python
from repom import BaseRepository, FilterParams

class TaskFilterParams(FilterParams):
    status: str | None = None
    title: str | None = None

class TaskRepository(BaseRepository[Task]):
    # フィールドとカラムのマッピングを置くだけ（既定は完全一致）
    field_to_column = {
        "status": Task.status,
        "title": Task.title,
    }

# 使い方
repo = TaskRepository()
tasks = repo.find(params=TaskFilterParams(status="active", title="task"), limit=100)
```

`find(params=..., filters=...)` では、`params` から生成した条件と `filters` の条件を AND で組み合わせるため、両方を渡すと結果がさらに絞り込まれます。`count_by_params()` も同じルールに従います。

### 未マッピングフィールド

デフォルトの `_build_filters()` は、値が `None` でない `FilterParams` フィールドに対応する
`field_to_column` のエントリがない、または対応する値が `None` の場合、Repository 名と
フィールド名を含む `ValueError` を送出します。該当するフィールドを
`field_to_column` に追加するか、`_build_filters()` をオーバーライドしてください。
マッピング済みフィールドを `super()._build_filters()` に委ねるオーバーライドでは、
残りのフィールドをそのオーバーライド側で処理します。`count_by_params()` も同じ規則です。

この規則は [BaseRepository](base_repository_guide.md)、
[AsyncBaseRepository](async_repository_guide.md)、
[Soft Delete](../model/soft_delete_guide.md) の検索にも適用されます。

`count(params=..., filters=...)` と `find_deleted(params=..., filters=...)` は、
`FilterParams` から生成したマッピング済み条件と明示的な SQL 式を AND で結合します。
`count_by_params()` は `count(params=...)` を呼び出すための簡便なラッパーです。

`field_to_column` では `gte_column()`、`gt_column()`、`lte_column()`、`lt_column()` を使って
範囲比較を指定できます。これらのヘルパーは、整数、日付、その他の比較可能な値に対して
`>=`、`>`、`<=`、`<` の比較を行います。LIKE 検索に適用される文字列長の上限は、
これらの比較には適用されません。

```python
from datetime import datetime, timezone

from repom import BaseRepository, FilterParams
from repom.repositories import gte_column, lt_column

class TaskFilterParams(FilterParams):
    created_at_from: datetime | None = None
    created_at_before: datetime | None = None

class TaskRepository(BaseRepository[Task]):
    field_to_column = {
        "created_at_from": gte_column(Task.created_at),
        "created_at_before": lt_column(Task.created_at),
    }

repo = TaskRepository()
start = datetime(2025, 1, 1, tzinfo=timezone.utc)
end = datetime(2025, 12, 31, tzinfo=timezone.utc)
tasks = repo.find(
    params=TaskFilterParams(created_at_from=start, created_at_before=end),
    limit=100,
)
```

部分一致・前方一致が必要な場合は `contains_column()` / `prefix_column()` で
明示してください。これらは SQL の `LIKE` を使いますが、値に含まれる `%` / `_`
はワイルドカードではなくリテラル文字として自動的にエスケープされます
（`contains()` の既定挙動である無エスケープの `LIKE` は、`%` 一文字で全件
ヒットしたり、交互ワイルドカードパターンでバックトラッキング DoS を招く
ため使いません）。長すぎる値はこの DoS を防ぐため `ValueError` で拒否され、
上限は `max_length` 引数で調整できます（既定 256 文字）。

```python
from repom import BaseRepository, FilterParams
from repom.repositories import contains_column, prefix_column

class TaskFilterParams(FilterParams):
    status: str | None = None
    title: str | None = None

class TaskRepository(BaseRepository[Task]):
    field_to_column = {
        "status": Task.status,                 # 完全一致
        "title": contains_column(Task.title),  # 部分一致（LIKE、エスケープ済み）
    }
```

**違いのまとめ**:

| 方式 | 用途 | コード量 | 柔軟性 |
|------|------|---------|--------|
| `field_to_column` マッピング | 等価・部分一致・IN・範囲比較 | 少ない | 低い |
| `_build_filters()` オーバーライド | OR、サブクエリなどの複雑な条件 | 多い | 高い |

**推奨**:
- ✅ シンプルな検索 → `field_to_column` マッピング
- 🔧 複雑な検索 → `_build_filters()` オーバーライド

---

## 高度な使い方

### リスト型パラメータ（複数選択）

リスト型フィールドは、`field_to_column` でカラムに対応付けると自動的に `IN` 検索に
なります。

```python
from repom import BaseRepository, FilterParams

class TaskFilterParams(FilterParams):
    status: list[str] | None = None
    priority: list[str] | None = None

class TaskRepository(BaseRepository[Task]):
    field_to_column = {
        "status": Task.status,
        "priority": Task.priority,
    }

repo = TaskRepository()
tasks = repo.find(
    params=TaskFilterParams(status=["active", "pending"], priority=["high"]),
    limit=100,
)
```

### 日付範囲検索

日付範囲は `gte_column()` / `lt_column()` を `field_to_column` に指定します。
実行できるコード例は、上記の[フィールドとカラムのマッピング](#方法2-field_to_column-マッピングシンプル)を参照してください。

---

## ベストプラクティス

### 1. FilterParams は軽量に保つ

```python
# ✅ 良い例
class TaskFilterParams(FilterParams):
    status: Optional[str] = None
    priority: Optional[str] = None

# ❌ 悪い例（多すぎる）
class TaskFilterParams(FilterParams):
    status: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    created_by: Optional[int] = None
    assigned_to: Optional[int] = None
    # ... 20個のフィールド
```

### 2. デフォルト値を設定

```python
class TaskFilterParams(FilterParams):
    status: str = "active"
```

このように `None` 以外のデフォルト値を持つフィールドも、デフォルトの検索条件 builder では
検索対象です。`status` を `field_to_column` に対応付けるか、`_build_filters()` で処理しないと、
`find(params=...)` は未マッピングフィールドの `ValueError` を送出します。

ページング値は `FilterParams` の検索条件ではありません。デフォルト builder を使う場合、
`limit` / `offset` は `FilterParams` subclass のフィールドに含めず、検索値の外で管理して
`find(limit=..., offset=...)` に渡してください。マッピング値が `None` のエントリも未マッピングと
同じ扱いです。ページング値を params に含める必要がある場合は `_build_filters()` を
オーバーライドし、検索フィールドは `super()._build_filters(params)` に委ねてください。

---

## 次のステップ

- **[基礎編：CRUD操作](base_repository_guide.md)** - リポジトリの基本的な使い方
- **[上級編：検索・フィルタ・options](repository_advanced_guide.md)** - 複雑な検索、eager loading、パフォーマンス最適化

## 関連ドキュメント

- **[auto_import_models ガイド](../features/auto_import_models_guide.md)**: モデルの自動インポート
- **[BaseRepository ソースコード](../../../repom/repositories/base_repository.py)**: 実装の詳細
