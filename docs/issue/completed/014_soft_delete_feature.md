# Issue #014: repom への論理削除（Soft Delete）機能追加

**ステータス**: ✅ 完了

**作成日**: 2025-12-10

**完了日**: 2025-12-10

**優先度**: 高

## 問題の説明

現在、repom には統一された削除機能が存在せず、各プロジェクトで独自に実装する必要があります。特に以下の課題があります：

- mine-py でアセット削除時に物理ファイルも削除する必要がある
- 誤削除からの復元機能が必要
- 論理削除 → バッチ処理での物理削除というフローを実現したい
- プロジェクトごとに削除処理の実装が異なり、統一性がない

## 提案される解決策

repom に **SoftDeletableMixin** と論理削除対応の Repository メソッドを追加し、全プロジェクトで統一された削除処理を提供します。

### 主要機能

1. **SoftDeletableMixin**: `deleted_at` カラムと削除操作メソッドを提供
2. **BaseRepository の拡張**: 論理削除対応メソッド群を追加
3. **自動フィルタリング**: `find()` が削除済みを自動除外
4. **復元機能**: 論理削除したレコードを復元可能
5. **物理削除**: 完全削除も可能

## 影響範囲

### 影響を受けるファイル

- `repom/mixins/soft_delete.py` - SoftDeletableMixin (Mixin 分離後)
- `repom/repositories/base_repository.py` - 論理削除メソッド追加
- `tests/unit_tests/test_soft_delete.py` - 新規テストファイル
- `docs/guides/model/soft_delete_guide.md` - 新規ガイド作成
- `README.md` - 機能説明追加

### 影響を受ける機能

- **既存機能への影響**: なし（後方互換性あり）
- **新規機能**: 論理削除を使いたいモデルが Mixin を継承可能
- **外部プロジェクト**: mine-py、その他の消費プロジェクトで利用可能

## 実装計画

### Phase 1: repom への基盤追加（高優先度）

1. **SoftDeletableMixin の実装**
   - `deleted_at` カラム定義
   - `soft_delete()` メソッド
   - `restore()` メソッド
   - `is_deleted` プロパティ

2. **BaseRepository の拡張**
   - `_has_soft_delete()` - Mixin 存在チェック
   - `find()` - 削除済み自動除外（既存メソッド修正）
   - `find_with_deleted()` - 削除済み含む検索
   - `get_by_id()` - 削除済み自動除外（既存メソッド修正）
   - `get_by_id_with_deleted()` - 削除済み含む取得
   - `soft_delete(id)` - 論理削除実行
   - `restore(id)` - 削除復元
   - `permanent_delete(id)` - 物理削除
   - `find_deleted()` - 削除済みのみ検索
   - `find_deleted_before(date)` - 指定日時より前の削除済みを検索

3. **テストケースの作成**
   - Mixin 基本機能テスト
   - Repository メソッドテスト
   - 自動フィルタリングテスト
   - エッジケーステスト

4. **ドキュメント作成**
   - `docs/guides/soft_delete_guide.md` 作成
   - README.md への機能説明追加
   - 使用例の記載

### Phase 2: mine-py での適用（中優先度）

1. **AssetItemModel への適用**
   - SoftDeletableMixin を継承
   - マイグレーション作成・実行

2. **AssetItemRepository の拡張**
   - `soft_delete_with_file_mark()` - 論理削除
   - `permanent_delete_with_file()` - ファイル含む物理削除
   - `get_assets_for_cleanup()` - クリーンアップ対象取得

3. **エンドポイント実装**
   - DELETE エンドポイント（論理削除）
   - POST /restore エンドポイント（復元）

### Phase 3: バッチ処理（低優先度）

1. **クリーンアップタスク作成**
   - 30日以上前の削除済みアセットを物理削除
   - ログ記録とエラーハンドリング

2. **スケジューラ登録**
   - 定期実行設定

## 実装の詳細

### 1. SoftDeletableMixin

```python
from datetime import datetime, timezone
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

class SoftDeletableMixin:
    """論理削除機能を提供する Mixin"""
    
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
        info={'description': '論理削除日時（NULL = 削除されていない）'}
    )
    
    def soft_delete(self) -> None:
        """論理削除を実行"""
        self.deleted_at = datetime.now(timezone.utc)
        
    def restore(self) -> None:
        """削除を取り消し"""
        self.deleted_at = None
        
    @property
    def is_deleted(self) -> bool:
        """削除済みかどうかを返す"""
        return self.deleted_at is not None
```

### 2. BaseRepository メソッド例

```python
def soft_delete(self, id: int) -> bool:
    """論理削除
    
    Args:
        id: 削除するレコードのID
        
    Returns:
        bool: 削除成功したか
        
    Raises:
        ValueError: モデルが SoftDeletableMixin を持たない場合
    """
    if not self._has_soft_delete():
        raise ValueError(
            f"{self.model_class.__name__} does not support soft delete. "
            "Add SoftDeletableMixin to the model."
        )
    
    item = self.get_by_id(id)
    if not item:
        return False
        
    item.soft_delete()
    self.session.commit()
    return True
```

### 3. 使用例（mine-py）

```python
# モデル定義
class AssetItemModel(BaseModelAuto, SoftDeletableMixin,
                     use_created_at=True, use_updated_at=True):
    __tablename__ = "asset_items"
    # ... フィールド定義

# Repository 使用
repo = AssetItemRepository()

# 論理削除
repo.soft_delete(asset_id)

# 復元
repo.restore(asset_id)

# 30日以上前に削除されたものを取得
from datetime import datetime, timedelta, timezone
threshold = datetime.now(timezone.utc) - timedelta(days=30)
old_deleted = repo.find_deleted_before(threshold)

# 物理削除（ファイルも削除）
for asset in old_deleted:
    repo.permanent_delete_with_file(asset.id)
```

## テスト計画

### テストケース

1. **SoftDeletableMixin テスト**
   - `soft_delete()` メソッドが `deleted_at` を設定
   - `restore()` メソッドが `deleted_at` をクリア
   - `is_deleted` プロパティが正しく動作

2. **BaseRepository 自動フィルタテスト**
   - `find()` が削除済みを除外
   - `find_with_deleted()` が全レコード取得
   - `get_by_id()` が削除済みを除外
   - `get_by_id_with_deleted()` が削除済みも取得

3. **削除・復元テスト**
   - `soft_delete()` が正しく論理削除
   - `restore()` が正しく復元
   - `permanent_delete()` が物理削除

4. **検索テスト**
   - `find_deleted()` が削除済みのみ取得
   - `find_deleted_before()` が日時フィルタ動作

5. **エラーハンドリングテスト**
   - Mixin 未継承モデルで `soft_delete()` を呼ぶと例外
   - 存在しない ID で操作すると False 返却

### テストファイル

- `tests/unit_tests/test_soft_delete.py` - 約8-10個のテストケース

### 期待されるテスト結果

- すべてのテストがパス
- カバレッジ 95% 以上
- エッジケースも網羅

## 期待される効果

1. **統一された削除処理**: 全プロジェクトで同じパターンが使える
2. **安全性向上**: 誤削除からの復元が可能
3. **コード削減**: 各プロジェクトで削除処理を実装する必要がない
4. **保守性向上**: 削除ロジックが repom に集約される
5. **拡張性**: 他のモデルでも簡単に論理削除を導入可能

## 既存データへの影響

- `deleted_at` カラムはデフォルト `NULL` なので、既存レコードは「削除されていない」扱い
- マイグレーション実行後も既存機能に影響なし
- **後方互換性あり**: SoftDeletableMixin を使わないモデルは従来通り動作

## 質問・確認事項

1. **API 設計について**:
   - `find()` が削除済みを自動除外する仕様で良いか？
   - 明示的に `find(include_deleted=True)` のような API が必要か？

2. **パフォーマンス**:
   - `deleted_at` カラムにインデックスを作成する想定だが、他に最適化が必要か？

3. **ロギング**:
   - 論理削除・復元・物理削除時のログレベルはどうするか？（INFO? WARNING?）

4. **エラーハンドリング**:
   - 論理削除非対応モデルで `soft_delete()` を呼んだ時に例外を投げる？それとも False を返す？
   - **提案**: 例外を投げる（ValueError）- 使用方法の誤りは早期に検出すべき

## 関連リソース

### 参考実装

- **Django の論理削除実装**: django-safedelete パッケージのアプローチ
- **Rails の論理削除**: paranoia gem のパターン
- **SQLAlchemy Mixin パターン**: https://docs.sqlalchemy.org/en/20/orm/declarative_mixins.html

### 関連 Issue

- mine-py: アセット削除時の物理ファイル削除処理
- mine-py: ani_video_asset_links 中間テーブルの管理

### 関連ドキュメント

- `docs/guides/base_model_auto_guide.md` - Mixin パターンの参考
- `docs/guides/repository_and_utilities_guide.md` - Repository 拡張の参考
- `docs/guides/testing_guide.md` - テスト戦略

---

## 実装結果

### ✅ 実装完了内容

**Phase 1: repom への基盤追加** - 完了

#### 1. SoftDeletableMixin の実装
- ✅ `repom/mixins/soft_delete.py` に追加 (Mixin 分離後)
- ✅ `deleted_at` カラム（DateTime(timezone=True)、インデックス付き）
- ✅ `soft_delete()` メソッド
- ✅ `restore()` メソッド
- ✅ `is_deleted` プロパティ
- ✅ ログ記録機能（INFO レベル）

#### 2. BaseRepository の拡張
- ✅ `repom/base_repository.py` を拡張
- ✅ `_has_soft_delete()` - Mixin 存在チェック
- ✅ `find(include_deleted=False)` - パラメータで制御
- ✅ `get_by_id(include_deleted=False)` - パラメータで制御
- ✅ `soft_delete(id)` - 論理削除実行
- ✅ `restore(id)` - 削除復元
- ✅ `permanent_delete(id)` - 物理削除（WARNING ログ）
- ✅ `find_deleted()` - 削除済みのみ検索
- ✅ `find_deleted_before(date)` - 日時フィルタ

#### 3. テストケース
- ✅ `tests/unit_tests/test_soft_delete.py` を作成
- ✅ **22テストケース、全パス**
- ✅ **既存260テストも全パス**（後方互換性確認済み）
- ✅ カバレッジ: Mixin、Repository、統合シナリオ全て網羅

#### 4. ドキュメント
- ✅ `docs/guides/soft_delete_guide.md` - 詳細ガイド作成
- ✅ `README.md` - 機能説明とガイドリンク追加

### 📊 テスト結果

```
tests/unit_tests/test_soft_delete.py - 22 passed
tests/unit_tests (全体) - 260 passed, 0 failed
```

### 🎯 実装した仕様（確定版）

| 項目 | 実装内容 |
|------|---------|
| **API 設計** | `find(include_deleted=False)` パラメータ方式 |
| **エラーハンドリング** | `ValueError` 例外（論理削除非対応モデル） |
| **ロギング** | INFO（論理削除・復元）/ WARNING（物理削除） |
| **インデックス** | `deleted_at` に自動的に `index=True` |
| **後方互換性** | ✅ 既存コード影響なし |

### 📚 成果物

1. **実装ファイル**
   - `repom/mixins/soft_delete.py` - SoftDeletableMixin 追加 (Mixin 分離後)
   - `repom/base_repository.py` - 論理削除メソッド追加

2. **テストファイル**
   - `tests/unit_tests/test_soft_delete.py` - 22テストケース

3. **ドキュメント**
   - `docs/guides/soft_delete_guide.md` - 完全ガイド
   - `README.md` - 機能説明セクション追加

### 🚀 次のステップ（mine-py での適用）

Phase 2 は別途実施予定：
1. AssetItemModel に SoftDeletableMixin 適用
2. マイグレーション作成・実行
3. Repository 拡張（ファイル削除ロジック）
4. バッチ処理実装

---

**次のステップ**: Phase 1 の実装開始（ユーザー承認後）
