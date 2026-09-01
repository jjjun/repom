# FilterParams ガイド

**目的**: 型安全な検索パラメータを Pydantic モデルとして定義する

**対象読者**: repom を使ってリポジトリ検索を実装する開発者・AI エージェント

**関連ドキュメント**:
- [基礎編：CRUD操作](base_repository_guide.md) - リポジトリの基本的な使い方
- [上級編：検索・フィルタ・options](repository_advanced_guide.md) - 複雑な検索、eager loading、パフォーマンス最適化

FastAPI のクエリパラメータへの変換（旧 `as_query_depends()`）は利用側フレーム
ワーク（fast-domain）に移管されました。このガイドでは repom に残る
`FilterParams` 本体の使い方（`find_by_params()` と組み合わせた検索）を説明し
ます。

---

## 📚 目次

1. [基本的な FilterParams](#基本的な-filterparams)
2. [カスタムリポジトリでの処理](#カスタムリポジトリでの処理)

---

## 基本的な FilterParams

```python
from repom import FilterParams
from typing import Optional

class TaskFilterParams(FilterParams):
    status: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None
```

```python
repo = TaskRepository()
tasks = repo.find_by_params(TaskFilterParams(status="active", priority="high"))
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
            filters.append(Task.title.like(f"%{params.title}%"))
        
        return filters
    
    def find_by_params(
        self,
        params: Optional[TaskFilterParams] = None,
        **kwargs
    ) -> List[Task]:
        """FilterParams を使って検索"""
        filters = self._build_filters(params)
        return self.find(filters=filters, **kwargs)
    
    def count_by_params(self, params: Optional[TaskFilterParams] = None) -> int:
        """FilterParams を使ってカウント"""
        filters = self._build_filters(params)
        return self.count(filters=filters)
```

### 方法2: `field_to_column` マッピング（シンプル）

等価・部分一致・リスト検索のみの場合は、マッピングだけで自動生成できます。

```python
from repom import BaseRepository, FilterParams

class TaskFilterParams(FilterParams):
    status: str | None = None
    title: str | None = None

class TaskRepository(BaseRepository[Task]):
    # フィールドとカラムのマッピングを置くだけ
    field_to_column = {
        "status": Task.status,
        "title": Task.title,
    }

# 使い方
repo = TaskRepository()
tasks = repo.find_by_params(TaskFilterParams(status="active", title="task"))
```

**違いのまとめ**:

| 方式 | 用途 | コード量 | 柔軟性 |
|------|------|---------|--------|
| `field_to_column` マッピング | シンプルな等価・部分一致・IN検索 | 少ない | 低い |
| `_build_filters()` オーバーライド | 複雑な条件（日付範囲、OR、サブクエリ） | 多い | 高い |

**推奨**:
- ✅ シンプルな検索 → `field_to_column` マッピング
- 🔧 複雑な検索 → `_build_filters()` オーバーライド

---

## 高度な使い方

### リスト型パラメータ（複数選択）

```python
from typing import List, Optional

class TaskFilterParams(FilterParams):
    status: Optional[List[str]] = None  # 複数ステータス
    priority: Optional[List[str]] = None

class TaskRepository(BaseRepository[Task]):
    def _build_filters(self, params: Optional[TaskFilterParams]) -> list:
        if not params:
            return []
        
        filters = []
        
        if params.status:
            # IN クエリ
            filters.append(Task.status.in_(params.status))
        
        if params.priority:
            filters.append(Task.priority.in_(params.priority))
        
        return filters
```

**クエリ例**:
```
GET /tasks?status=active&status=pending&priority=high
```

### 日付範囲検索

```python
from datetime import datetime
from typing import Optional

class TaskFilterParams(FilterParams):
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

class TaskRepository(BaseRepository[Task]):
    def _build_filters(self, params: Optional[TaskFilterParams]) -> list:
        if not params:
            return []
        
        filters = []
        
        if params.created_after:
            filters.append(Task.created_at >= params.created_after)
        
        if params.created_before:
            filters.append(Task.created_at <= params.created_before)
        
        return filters
```

**クエリ例**:
```
GET /tasks?created_after=2025-01-01T00:00:00&created_before=2025-12-31T23:59:59
```

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
    status: str = "active"  # デフォルトはアクティブのみ
    limit: int = 10
    offset: int = 0
```

---

## 次のステップ

- **[基礎編：CRUD操作](base_repository_guide.md)** - リポジトリの基本的な使い方
- **[上級編：検索・フィルタ・options](repository_advanced_guide.md)** - 複雑な検索、eager loading、パフォーマンス最適化

## 関連ドキュメント

- **[auto_import_models ガイド](../features/auto_import_models_guide.md)**: モデルの自動インポート
- **[BaseRepository ソースコード](../../../repom/repositories/base_repository.py)**: 実装の詳細

---

**最終更新**: 2025-12-28  
**対象バージョン**: repom v2.0+
