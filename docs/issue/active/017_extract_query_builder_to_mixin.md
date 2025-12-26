# Issue #017: クエリ構築機能のMixin化によるコード一貫性向上

**ステータス**: 🔴 未着手

**作成日**: 2025-12-26

**優先度**: 低

**複雑度**: 低

## 問題の説明

現在、`BaseRepository` と `AsyncBaseRepository` に以下のクエリ構築関連メソッドが重複実装されています：

1. `set_find_option()` - クエリにオプション設定（約10行のラッパー）
2. `parse_order_by()` - order_by 文字列をパース（約10行のラッパー）
3. `_build_filters()` - FilterParams からフィルタ条件構築（約5行のデフォルト実装）
4. `allowed_order_columns` - ソート可能カラムのホワイトリスト

### 現状の課題

- **コードの重複**: 両リポジトリで同一の実装が存在（合計約25行）
- **一貫性の欠如**: 論理削除機能は Mixin 化済みだが、クエリ構築は未整理
- **意図の不明確さ**: 同期・非同期で同じ処理を使っていることが明示されていない

### 影響を受けるファイル

- `repom/repositories/base_repository.py` (約25行)
- `repom/repositories/async_base_repository.py` (約25行)

## 提案される解決策

**Mixin パターン**を採用し、クエリ構築関連機能を独立したモジュールに切り出します。

### ファイル構成

```
repom/
└── repositories/
    ├── _core.py                    # 共通関数（既存）
    ├── _soft_delete.py             # 論理削除ミックスイン（既存）
    ├── _query_builder.py           # クエリ構築ミックスイン（新規）
    ├── base_repository.py          # QueryBuilderMixin を継承
    └── async_base_repository.py    # QueryBuilderMixin を継承
```

### 新規ファイル: `repom/repositories/_query_builder.py`

```python
"""
リポジトリのクエリ構築機能ミックスイン

BaseRepository と AsyncBaseRepository で共有される
クエリ構築・フィルタリング関連のメソッドを提供します。

このミックスインは同期・非同期に関わらず使用できる設計です。
"""

from typing import Optional
from repom.repositories._core import parse_order_by, set_find_option, FilterParams


class QueryBuilderMixin:
    """クエリ構築関連の共通機能
    
    BaseRepository と AsyncBaseRepository で共有される
    クエリ構築・フィルタリング関連のメソッドを提供。
    
    Attributes:
        allowed_order_columns: ソート可能なカラムのホワイトリスト（サブクラスで拡張可能）
    """
    
    # Default allowed columns for order_by operations (can be extended by subclasses)
    allowed_order_columns = [
        'id', 'title', 'created_at', 'updated_at',
        'started_at', 'finished_at', 'executed_at'
    ]
    
    def set_find_option(self, query, **kwargs):
        """クエリにオプションを設定するメソッド（_core.set_find_option を呼び出し）

        Args:
            query: SQLAlchemy のクエリオブジェクト
            **kwargs: offset, limit, order_by, options

        Returns:
            オプション設定済みのクエリオブジェクト
        """
        return set_find_option(query, self.model, self.allowed_order_columns, **kwargs)
    
    def parse_order_by(self, model_class, order_by_str: str):
        """Parse order_by string（_core.parse_order_by を呼び出し）

        Args:
            model_class: The SQLAlchemy model class
            order_by_str: Order specification string (e.g., "created_at:desc")

        Returns:
            SQLAlchemy column expression with asc() or desc()
        """
        return parse_order_by(model_class, order_by_str, self.allowed_order_columns)
    
    def _build_filters(self, params: Optional[FilterParams]) -> list:
        """FilterParams からフィルタ条件を構築

        サブクラスでオーバーライドして独自のフィルタロジックを実装できます。

        Args:
            params: フィルタパラメータ

        Returns:
            list: フィルタ条件のリスト
        """
        # デフォルトは何もフィルタしない
        return []
```

### 修正後のリポジトリ

```python
# repom/repositories/base_repository.py
from repom.repositories._soft_delete import SoftDeleteRepositoryMixin
from repom.repositories._query_builder import QueryBuilderMixin

class BaseRepository(SoftDeleteRepositoryMixin[T], QueryBuilderMixin, Generic[T]):
    """同期版ベースリポジトリ
    
    - SoftDeleteRepositoryMixin により論理削除機能を提供
    - QueryBuilderMixin によりクエリ構築機能を提供
    """
    # set_find_option, parse_order_by, _build_filters は Mixin から継承
    ...


# repom/repositories/async_base_repository.py
from repom.repositories._soft_delete import AsyncSoftDeleteRepositoryMixin
from repom.repositories._query_builder import QueryBuilderMixin

class AsyncBaseRepository(AsyncSoftDeleteRepositoryMixin[T], QueryBuilderMixin, Generic[T]):
    """非同期版ベースリポジトリ
    
    - AsyncSoftDeleteRepositoryMixin により論理削除機能を提供
    - QueryBuilderMixin によりクエリ構築機能を提供
    """
    # set_find_option, parse_order_by, _build_filters は Mixin から継承
    ...
```

## メリット

1. **一貫性**: 論理削除ミックスインと同じパターンで統一
2. **明示性**: 同期・非同期で**同じ処理を使っている**ことが明確
3. **DRY原則**: 重複コード削減（各リポジトリから約25行削減）
4. **保守性**: クエリ構築ロジックの変更は1ファイルのみ
5. **拡張性**: 将来のクエリ構築機能追加が容易
6. **テスト**: ミックスイン単体でテスト可能

## デメリット

1. **ファイル増加**: ファイルが1つ増える（ただし構造は明確化）
2. **多重継承**: 継承チェーンがやや複雑に（3つの親クラス）

## 影響範囲

### 新規作成

- `repom/repositories/_query_builder.py` (約50行)

### 修正

- `repom/repositories/base_repository.py` (約25行削減)
- `repom/repositories/async_base_repository.py` (約25行削減)

### 影響なし

- 外部 API は変更なし（既存コードはそのまま動作）
- テストコードは変更不要

## 実装計画

### Phase 1: ミックスイン作成

1. `repom/repositories/_query_builder.py` を作成
2. `QueryBuilderMixin` を実装
3. `allowed_order_columns`, `set_find_option()`, `parse_order_by()`, `_build_filters()` を移動

### Phase 2: リポジトリ修正

4. `BaseRepository` から該当メソッドを削除し、`QueryBuilderMixin` を継承
5. `AsyncBaseRepository` から該当メソッドを削除し、`QueryBuilderMixin` を継承

### Phase 3: テスト

6. 既存の全テストがパスすることを確認（409 tests）
7. 必要に応じてミックスイン単体のテストを追加

### Phase 4: ドキュメント更新

8. AGENTS.md の構造説明を更新
9. コード内のドキュメント文字列を整理

## テスト計画

### 既存テストの実行

- `poetry run pytest tests/unit_tests` - 全テストパス確認（409 tests）
- クエリ構築関連のテストが全てパスすることを確認

### 新規テスト（オプション）

- ミックスイン単体のテスト（必要に応じて）

## 完了基準

- ✅ `_query_builder.py` が作成され、全クエリ構築機能が実装されている
- ✅ `BaseRepository` と `AsyncBaseRepository` から該当メソッドが削除され、ミックスインを継承している
- ✅ 既存の全テストがパスする
- ✅ コードレビューで問題が指摘されていない
- ✅ 外部 API に破壊的変更がない
- ✅ AGENTS.md の構造説明が更新されている

## 関連ドキュメント

- **論理削除ミックスイン**: `repom/repositories/_soft_delete.py`
- **共通関数**: `repom/repositories/_core.py`
- **ベースリポジトリ**: `repom/repositories/base_repository.py`
- **非同期リポジトリ**: `repom/repositories/async_base_repository.py`
- **Issue #015**: [completed/015_extract_soft_delete_to_mixin.md](../completed/015_extract_soft_delete_to_mixin.md) - 論理削除ミックスイン化（同じパターン）

## 備考

### 設計上の意図

このミックスイン化の主な目的は、**一貫性と明示性の向上**です：

1. **一貫性**: 論理削除機能（Issue #015）と同じパターンで整理
2. **明示性**: 同期・非同期リポジトリで**同じクエリ構築処理**を使っていることを明確化
3. **保守性**: 将来的なクエリ構築ロジックの変更を一箇所で管理

### 実装の軽量性

- 実装はほぼラッパーメソッドのみ（実体は `_core.py` の関数）
- 削減できる行数は少ないが、構造の明確化が主目的
- アンダースコアプレフィックス（`_query_builder.py`）により、内部実装であることを明示

### 継承構造

```python
# BaseRepository
BaseRepository(SoftDeleteRepositoryMixin[T], QueryBuilderMixin, Generic[T])
    ↑                    ↑                         ↑
    |                    |                         +-- クエリ構築（新規）
    |                    +-- 論理削除（Issue #015）
    +-- ベースリポジトリ

# AsyncBaseRepository
AsyncBaseRepository(AsyncSoftDeleteRepositoryMixin[T], QueryBuilderMixin, Generic[T])
    ↑                          ↑                           ↑
    |                          |                           +-- クエリ構築（新規）
    |                          +-- 非同期論理削除（Issue #015）
    +-- 非同期ベースリポジトリ
```

### 多重継承の順序

- 論理削除ミックスイン（型パラメータあり）を最初に継承
- クエリ構築ミックスイン（型パラメータなし）を2番目に継承
- Python の MRO (Method Resolution Order) により、メソッド検索は左から右へ
