# Issue #015: 論理削除機能のMixin化によるコード可読性向上

**ステータス**: ✅ 完了

**作成日**: 2025-12-26

**完了日**: 2025-12-26

**優先度**: 中

**複雑度**: 中

## 問題の説明

現在、`BaseRepository` と `AsyncBaseRepository` には論理削除関連のメソッド（約150行）が直接実装されており、以下の問題があります：

1. **コードの肥大化**: 各リポジトリファイルが約500行を超え、見通しが悪い
2. **責任の分離不足**: 論理削除機能がリポジトリ本体と混在している
3. **メンテナンス性**: 論理削除機能の変更時に2ファイルを同時に修正する必要がある
4. **テスタビリティ**: 論理削除機能を独立してテストしにくい

### 影響を受けるファイル

- `repom/repositories/base_repository.py` (約500行)
- `repom/repositories/async_base_repository.py` (約530行)

### 論理削除関連メソッド（各ファイルに重複実装）

- `soft_delete(id)` - 論理削除実行
- `restore(id)` - 削除を復元
- `permanent_delete(id)` - 物理削除
- `find_deleted()` - 削除済みレコード取得
- `find_deleted_before(date)` - 指定日時前の削除レコード取得

## 提案される解決策

**Mixin パターン**を採用し、論理削除機能を独立したモジュールに切り出します。

### ファイル構成

```
repom/
├── mixins/
│   └── soft_delete.py              # モデル用（既存）
└── repositories/
    ├── _core.py                    # 共通関数（既存）
    ├── _soft_delete.py             # リポジトリ用ミックスイン（新規）
    ├── base_repository.py          # SoftDeleteRepositoryMixin を継承
    └── async_base_repository.py    # AsyncSoftDeleteRepositoryMixin を継承
```

### 新規ファイル: `repom/repositories/_soft_delete.py`

```python
"""
リポジトリの論理削除機能ミックスイン

モデル用ミックスイン（repom.mixins.soft_delete）とは別に、
リポジトリレイヤーでの論理削除操作を提供します。
"""

from typing import TypeVar, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import logging

T = TypeVar('T')
logger = logging.getLogger(__name__)


class SoftDeleteRepositoryMixin:
    """同期版リポジトリの論理削除機能
    
    BaseRepository と組み合わせて使用します。
    """
    
    def soft_delete(self, id: int) -> bool:
        """論理削除を実行"""
        ...
    
    def restore(self, id: int) -> bool:
        """削除を復元"""
        ...
    
    def permanent_delete(self, id: int) -> bool:
        """物理削除"""
        ...
    
    def find_deleted(self, ...) -> List[T]:
        """削除済みレコードのみ取得"""
        ...
    
    def find_deleted_before(self, before_date: datetime, ...) -> List[T]:
        """指定日時より前に削除されたレコードを取得"""
        ...


class AsyncSoftDeleteRepositoryMixin:
    """非同期版リポジトリの論理削除機能
    
    AsyncBaseRepository と組み合わせて使用します。
    """
    
    async def soft_delete(self, id: int) -> bool:
        """論理削除を実行"""
        ...
    
    async def restore(self, id: int) -> bool:
        """削除を復元"""
        ...
    
    async def permanent_delete(self, id: int) -> bool:
        """物理削除"""
        ...
    
    async def find_deleted(self, ...) -> List[T]:
        """削除済みレコードのみ取得"""
        ...
    
    async def find_deleted_before(self, before_date: datetime, ...) -> List[T]:
        """指定日時より前に削除されたレコードを取得"""
        ...
```

### 修正後のリポジトリ

```python
# repom/repositories/base_repository.py
from repom.repositories._soft_delete import SoftDeleteRepositoryMixin

class BaseRepository(SoftDeleteRepositoryMixin, Generic[T]):
    """同期版ベースリポジトリ
    
    SoftDeleteRepositoryMixin により論理削除機能を提供します。
    """
    # 論理削除メソッドは Mixin から継承
    # ここには基本的な CRUD のみ
    ...


# repom/repositories/async_base_repository.py
from repom.repositories._soft_delete import AsyncSoftDeleteRepositoryMixin

class AsyncBaseRepository(AsyncSoftDeleteRepositoryMixin, Generic[T]):
    """非同期版ベースリポジトリ
    
    AsyncSoftDeleteRepositoryMixin により論理削除機能を提供します。
    """
    # 論理削除メソッドは Mixin から継承
    # ここには基本的な CRUD のみ
    ...
```

## メリット

1. **責任の分離**: 論理削除機能が独立したモジュールに
2. **コード見通し向上**: 各リポジトリが約350行に削減（150行削減）
3. **メンテナンス性向上**: 論理削除機能の変更は1ファイルのみ
4. **テスタビリティ**: ミックスインを独立してテスト可能
5. **将来の拡張性**: 他の機能（監査ログ等）も同様のパターンで追加可能
6. **一貫性**: 既存の `_core.py` パターンと統一

## デメリット

1. **多重継承**: Python では一般的だが、継承順序に注意が必要
2. **ファイル分割**: ファイル数が1つ増える（ただし全体の見通しは向上）

## 影響範囲

### 新規作成

- `repom/repositories/_soft_delete.py` (約250行)

### 修正

- `repom/repositories/base_repository.py` (約150行削減: 500行 → 350行)
- `repom/repositories/async_base_repository.py` (約150行削減: 530行 → 380行)

### 影響なし

- 外部 API は変更なし（既存コードはそのまま動作）
- テストコードは変更不要

## 実装計画

### Phase 1: ミックスイン作成

1. `repom/repositories/_soft_delete.py` を作成
2. `SoftDeleteRepositoryMixin` を実装（同期版）
3. `AsyncSoftDeleteRepositoryMixin` を実装（非同期版）

### Phase 2: リポジトリ修正

4. `BaseRepository` から論理削除メソッドを削除し、ミックスインを継承
5. `AsyncBaseRepository` から論理削除メソッドを削除し、ミックスインを継承

### Phase 3: テスト

6. 既存の論理削除テストが全てパスすることを確認
7. 必要に応じてミックスイン単体のテストを追加

### Phase 4: ドキュメント更新

8. AGENTS.md の構造説明を更新（該当箇所は既に更新済み）
9. コード内のドキュメント文字列を整理

## テスト計画

### 既存テストの実行

- `tests/unit_tests/test_base_repository_soft_delete.py` - 全テストパス確認
- `tests/unit_tests/test_async_repository_soft_delete.py` - 全テストパス確認

### 新規テスト（オプション）

- ミックスイン単体のテスト（必要に応じて）

## 完了基準

- ✅ `_soft_delete.py` が作成され、全論理削除機能が実装されている
- ✅ `BaseRepository` と `AsyncBaseRepository` から論理削除メソッドが削除され、ミックスインを継承している
- ✅ 既存の論理削除関連テストが全てパスする
- ✅ コードレビューで問題が指摘されていない
- ✅ 外部 API に破壊的変更がない

## 関連ドキュメント

- **モデル用ミックスイン**: `repom/mixins/soft_delete.py`
- **ベースリポジトリ**: `repom/repositories/base_repository.py`
- **非同期リポジトリ**: `repom/repositories/async_base_repository.py`
- **共通関数**: `repom/repositories/_core.py`
- **Issue #014**: [completed/014_soft_delete_feature.md](../completed/014_soft_delete_feature.md) - 論理削除機能の最初の実装

## 備考

- アンダースコアプレフィックス（`_soft_delete.py`）により、内部実装であることを明示
- 既存の `_core.py` と同じパターンで配置
- `repom.mixins.soft_delete` はモデル用、`repom.repositories._soft_delete` はリポジトリ用と明確に分離
