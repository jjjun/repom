# Issue #022: isolated_mapper_registry フィクスチャの設計改善

**ステータス**: 📝 調査待機中  
**作成日**: 2026-01-28  
**優先度**: 低  
**複雑度**: 高

## 概要

`isolated_mapper_registry` フィクスチャは、repom のモデルのみをロードする設計のため、behavior_tests のモジュールレベルモデルがある場合に正しく動作しない問題。

**現状**: 一部のテストでのみ動作、Issue #021 で回避策を実装済み  
**提案**: フィクスチャの設計改善または代替アプローチの検討

## 問題の説明

### 現在の動作

**isolated_mapper_registry の処理フロー**:
1. clear_mappers() でマッパーをクリア
2. behavior_test_modules のモジュールを再ロード
3. `load_models()` で repom のモデルを再ロード（重要）
4. configure_mappers() でマッパーを再構築
5. テーブルを再作成

### 問題点

**load_models() は repom のモデルのみをロードする**:

```python
# repom/utility.py
def load_models(context: Optional[str] = None) -> None:
    if config.model_locations:
        auto_import_models_from_list(
            package_names=config.model_locations,  # デフォルトは ['repom.models']
            ...
        )
```

**結果**:
- behavior_tests のモジュールレベルモデル（例: test_date_type_comparison の TaskDateModel）が検出されない
- モジュール再ロード後、マッパーが再構築されない
- テストが `UnmappedInstanceError` で失敗

### 現在の使用状況

#### ✅ 正常動作するケース

**test_type_checking_detailed.py**, **test_type_checking_import_order.py**
- テスト関数内でモデルを定義
- isolated_mapper_registry が正常に機能

```python
def test_sqlalchemy_relationship_lazy_resolution(isolated_mapper_registry):
    # テスト関数内でモデル定義
    from tests.fixtures.type_checking import a_parent, z_child
    # ...
```

#### ❌ 動作しないケース（Issue #021 で発見）

**test_date_type_comparison.py**（Issue #021 解決前）
- モジュールレベルでモデルを定義
- isolated_mapper_registry が動作しない

```python
# モジュールレベル
class TaskDateModel(TaskModel):
    __tablename__ = 'task_date'
    # ...

def test_compare_save_behavior(isolated_mapper_registry, db_test):
    # TaskDateModel を使用（UnmappedInstanceError）
```

**Issue #021 の解決策**: テスト関数内でのローカルモデル再定義（回避策）

---

## 根本原因

### 1. load_models() の制限

`load_models()` は `config.model_locations` に基づいてモデルをロードしますが、これはデフォルトで `['repom.models']` のみを対象としています。

### 2. behavior_test_modules の再ロード

conftest.py では `behavior_test_modules` リストのモジュールを再ロードしますが:

```python
behavior_test_modules = [
    'tests.behavior_tests.test_date_type_comparison',  # 再ロードされる
    'tests.behavior_tests.test_migration_no_id',
]
```

再ロード後、`load_models()` では検出されないため、マッパーが再構築されません。

### 3. 設計上の制約

isolated_mapper_registry は以下を想定:
- テスト関数内でモデル定義
- repom のモデルのみを使用

モジュールレベルモデルは想定外。

---

## 提案される解決策

### 案1: load_models() の拡張（推奨度：中）

**アプローチ**:
- behavior_test_modules のモデルも検出できるように load_models() を拡張
- または、isolated_mapper_registry 内で別のロードロジックを追加

**メリット**:
- ✅ モジュールレベルモデルに対応
- ✅ 既存の設計を活かせる

**デメリット**:
- ❌ load_models() の複雑性増加
- ❌ behavior_tests の構造に依存

**実装例**:
```python
# isolated_mapper_registry 内
for module_name in behavior_test_modules:
    module = sys.modules[module_name]
    # モジュール内のモデルを明示的に検出・登録
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, Base):
            # マッパーを再構築
            configure_mappers()
```

### 案2: フィクスチャのスコープ変更（推奨度：低）

**アプローチ**:
- isolated_mapper_registry をテスト関数内モデル専用とする
- モジュールレベルモデルは別のアプローチ（Issue #021 の解決策）を使用

**メリット**:
- ✅ シンプルで理解しやすい
- ✅ 既存の動作を維持

**デメリット**:
- ❌ モジュールレベルモデルには非対応（現状維持）
- ❌ 制約が明示されていない

### 案3: ドキュメント整備のみ（推奨度：高）

**アプローチ**:
- isolated_mapper_registry の制約をドキュメントに明記
- モジュールレベルモデルを使用する場合は Issue #021 のパターンを推奨

**メリット**:
- ✅ 実装不要
- ✅ 回避策が既に存在
- ✅ シンプル

**デメリット**:
- ❌ 根本的な解決ではない

**実装例**:
```python
def isolated_mapper_registry(db_test):
    """一時的なモデル定義用のフィクスチャ
    
    【重要な制約】:
    - テスト関数内でモデルを定義する場合に使用してください
    - モジュールレベルでモデルを定義する場合は動作しません
    - モジュールレベルモデルを使用する場合は、各テスト関数内で
      ローカルモデルを再定義してください（test_unique_key_handling.py 参照）
    
    使用例:
        def test_temporary_model(isolated_mapper_registry, db_test):
            from repom.models.base_model import BaseModel
            
            class TempModel(BaseModel):
                __tablename__ = 'temp_table'
                name: Mapped[str] = mapped_column(String(100))
            
            # ...
    """
```

---

## 影響範囲

### 修正が必要なファイル

- **tests/conftest.py** - isolated_mapper_registry の実装
- **docs/guides/testing/isolated_mapper_fixture.md** - ドキュメント更新

### 影響を受けるテスト

- ✅ test_type_checking_detailed.py - 影響なし（既に正常動作）
- ✅ test_type_checking_import_order.py - 影響なし（既に正常動作）
- ✅ test_date_type_comparison.py - 影響なし（Issue #021 で回避策実装済み）

---

## 実装計画

### フェーズ1: 調査（優先）

- [ ] isolated_mapper_registry の使用状況を全テストで確認
- [ ] 実際に問題が発生しているケースをリストアップ
- [ ] パフォーマンスへの影響を測定

### フェーズ2: ドキュメント整備

- [ ] conftest.py の isolated_mapper_registry にドキュメントコメント追加
- [ ] docs/guides/testing/isolated_mapper_fixture.md を更新
- [ ] 制約と回避策を明記

### フェーズ3: 実装（オプション）

案1または案2を選択して実装（必要な場合のみ）

---

## 関連ドキュメント

- **Issue #021** - テスト間のマッパークリア干渉問題（回避策実装済み）
- **test_unique_key_handling.py** - ローカルモデル再定義パターンの実装例
- **tests/conftest.py** - isolated_mapper_registry の実装
- **docs/guides/testing/isolated_mapper_fixture.md** - フィクスチャガイド

---

## 備考

### 優先度が低い理由

1. **回避策が存在**: Issue #021 で実証済みの解決策がある
2. **実際の影響が限定的**: ほとんどのテストで問題なく動作
3. **設計変更のリスク**: 改善による副作用の可能性

### 将来的な改善

- behavior_tests のモデル構造を標準化
- テスト関数内モデル定義をベストプラクティスとして推奨
- モジュールレベルモデルを段階的に削減

---

## 次のアクション

1. ドキュメント整備を優先（案3）
2. 必要に応じて案1の実装を検討
3. 新しいテストでは必ずテスト関数内モデル定義を使用
