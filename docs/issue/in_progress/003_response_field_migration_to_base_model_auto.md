# Issue #3: response_field 機能を BaseModelAuto に移行

## Status
- **Created**: 2025-11-14
- **Priority**: High
- **Complexity**: High
- **Type**: Feature Migration / Breaking Change

## Problem Description

現在、Response スキーマ生成機能（`@response_field` デコレータと `get_response_schema()` メソッド）は `BaseModel` に実装されていますが、Create/Update スキーマ生成機能は `BaseModelAuto` にあります。

API スキーマ生成機能を一元化するため、Response スキーマ生成も `BaseModelAuto` に移行すべきです。

## Current State

### BaseModel (`repom/base_model.py`)
- `@response_field` デコレータ: `to_dict()` の追加フィールドを宣言
- `get_response_schema()`: Response スキーマを自動生成
- グローバルレジストリ: `_EXTRA_FIELDS_REGISTRY`

### BaseModelAuto (`repom/base_model_auto.py`)
- `get_create_schema()`: Create スキーマを自動生成
- `get_update_schema()`: Update スキーマを自動生成
- Column の `info` パラメータでスキーマ生成を制御:
  - `in_create`: Create スキーマに含めるか
  - `in_update`: Update スキーマに含めるか
  - `description`: フィールドの説明

## Desired State

### BaseModelAuto に統合
- `@response_field` デコレータを移行
- `get_response_schema()` メソッドを移行
- `info['in_response']` パラメータを追加してResponse スキーマ生成を制御

### BaseModel からは削除
- `@response_field` デコレータを削除
- `get_response_schema()` メソッドを削除
- `_EXTRA_FIELDS_REGISTRY` を BaseModelAuto に移動

## Design Decisions

### 1. デコレータの呼び出し方法
移行後は `@BaseModelAuto.response_field(...)` として使用:
```python
class MyModel(BaseModelAuto):
    @BaseModelAuto.response_field(extra_field=str)
    def to_dict(self):
        ...
```

### 2. 互換性
**破壊的変更**: `BaseModel` から機能を完全に削除
- 既存コードは動かなくなる
- プロジェクト側で修正が必要（mine_py など）

### 3. `info['in_response']` のデフォルト動作

#### 基本ルール
- **デフォルト**: `True`（Response に含める）
- **明示的除外**: `info={'in_response': False}` で除外

#### フィールド別の扱い

| フィールド種別 | Create | Update | Response | 理由 |
|--------------|--------|--------|----------|------|
| `id` | ❌ 除外 | ❌ 除外 | ✅ 含める | 自動生成、主キー |
| `created_at` | ❌ 除外 | ❌ 除外 | ✅ 含める | 自動設定、不変 |
| `updated_at` | ❌ 除外 | ❌ 除外 | ✅ 含める | 自動更新 |
| **外部キー (`*_id`)** | ✅ 含める | ✅ 含める | ✅ 含める | リレーション指定/変更に必要 |
| 通常カラム | ✅ 含める | ✅ 含める | ✅ 含める | ユーザーデータ |
| `@response_field` 追加フィールド | - | - | ✅ 常に含める | 明示的に宣言されたフィールド |
| `info={'in_*': False}` | ❌ 除外 | ❌ 除外 | ❌ 除外 | セキュリティ上の理由（例: `password_hash`） |

#### 外部キーの扱いに関する設計方針

**デフォルト**: 外部キーは Create/Update に含める（柔軟性重視）

**理由**:
1. **標準的なアプローチ**: GitHub API、Stripe API、Twitter API などの主要 API も同様
2. **柔軟性**: リソース作成時に関連を指定、更新時に関連を変更できる
3. **セキュリティ**: スキーマ除外ではなく、バリデーションと認可で対応

**セキュリティ対策**:
- **バリデーション**: 外部キーが存在するか確認（Validator Mixin）
- **認可チェック**: ユーザーが指定した関連リソースへのアクセス権を確認（FastAPI エンドポイント）
- **監査ログ**: 外部キーの変更を記録

**センシティブな外部キー**（所有者など）の扱い:
```python
owner_id = Column(
    Integer,
    ForeignKey('users.id'),
    info={
        'in_create': False,  # ❌ Create では受け取らない（認証から自動設定）
        'in_update': False,  # ❌ Update では変更不可（所有者変更は別エンドポイント）
        'in_response': True, # ✅ Response には含める（読み取り可能）
        'description': '所有者ID（システム設定）'
    }
)

#### 除外の使用例
```python
class UserModel(BaseModelAuto):
    __tablename__ = 'users'
    
    email = Column(String(255), info={'description': 'メールアドレス'})
    
    # セキュリティ上の理由で Response から除外
    password_hash = Column(
        String(255),
        info={
            'in_create': False,  # Create では受け取らない
            'in_update': False,  # Update でも受け取らない
            'in_response': False,  # Response にも含めない
            'description': 'パスワードハッシュ'
        }
    )
    
    # センシティブな外部キー: 所有者は変更不可
    owner_id = Column(
        Integer,
        ForeignKey('organizations.id'),
        info={
            'in_create': False,  # ❌ 認証から自動設定
            'in_update': False,  # ❌ 所有者変更は別エンドポイント
            'in_response': True, # ✅ 読み取りは可能
            'description': '所属組織ID（システム設定）'
        }
    )
    
    # 通常の外部キー: 作成・変更可能
    department_id = Column(
        Integer,
        ForeignKey('departments.id'),
        info={
            'in_create': True,   # ✅ 作成時に指定可能
            'in_update': True,   # ✅ 更新時に変更可能
            'in_response': True, # ✅ Response に含める
            'description': '部署ID'
        }
    )
```

## Implementation Plan

### Phase 1: 調査と準備
- [x] 現在の `BaseModel.get_response_schema()` の動作を調査
- [x] `_EXTRA_FIELDS_REGISTRY` の使用箇所を確認
- [x] 既存テストの洗い出し
- [x] 移行に必要な変更箇所を特定
- [ ] **注意**: `_EXTRA_FIELDS_REGISTRY` は BaseModel から完全に削除する（一気に書き換え予定のため、互換性は不要）

**調査結果**:

1. **`BaseModel.get_response_schema()` の実装**:
   - ファイル: `repom/base_model.py` (lines 217-393)
   - 主要メソッド:
     * `response_field()` デコレータ (lines 174-214)
     * `get_response_schema()` (lines 217-393)
     * `get_extra_fields_debug()` (line 392)
   - グローバルレジストリ: `_EXTRA_FIELDS_REGISTRY` (line 12)

2. **`_EXTRA_FIELDS_REGISTRY` の使用箇所**:
   - 定義: line 12
   - 登録: lines 253, 256
   - 参照: lines 295, 392
   - **合計**: 5箇所（すべて `base_model.py` 内）

3. **既存テストファイル**:
   - `tests/unit_tests/test_response_field.py` - `@response_field` デコレータのテスト
   - `tests/unit_tests/test_response_schema_forward_refs.py` - 前方参照解決のテスト
   - `tests/unit_tests/test_response_schema_fastapi.py` - FastAPI統合テスト
   - **すべて BaseModel を使用** → BaseModelAuto への移行が必要

4. **外部プロジェクトへの影響**:
   - mine_py プロジェクトで `@response_field` と `get_response_schema()` を使用
   - 一括移行が必要（破壊的変更）

5. **BaseModelAuto の現状**:
   - ファイル: `repom/base_model_auto.py`
   - 既存機能: `get_create_schema()`, `get_update_schema()`
   - `_should_exclude_from_schema()` メソッドあり（拡張が必要）
   - スキーマキャッシュ: `_create_schemas`, `_update_schemas` 辞書

### Phase 2: BaseModelAuto への移行
- [x] `BaseModelAuto` に `@response_field` デコレータを追加
- [x] `BaseModelAuto` に `get_response_schema()` メソッドを追加
- [x] `_EXTRA_FIELDS_REGISTRY` を `BaseModelAuto` に移動
- [x] `info['in_response']` のサポートを実装（次のPhaseで拡張）

**実装内容**:

1. **`_EXTRA_FIELDS_REGISTRY` の追加**:
   - `base_model_auto.py` にグローバルレジストリを追加（line ~37）
   - `WeakKeyDictionary` でメモリリークを防止

2. **`response_field()` デコレータの追加**:
   - `BaseModelAuto.response_field()` クラスメソッドを実装
   - `to_dict()` メソッドにメタデータを付与

3. **`get_response_schema()` メソッドの追加**:
   - カラムフィールドの自動取得
   - `@response_field` デコレータからの追加フィールド取得
   - 前方参照の解決サポート
   - スキーマキャッシュ機構

4. **`get_extra_fields_debug()` メソッドの追加**:
   - デバッグ用のヘルパーメソッド

5. **テスト結果**:
   - `test_response_field.py`: 13/13 パス ✅
   - 既存の BaseModel 機能は維持されている

### Phase 2.5: システムカラムの自動更新と保護
- [x] `updated_at` の自動更新を実装:
  - SQLite: SQLAlchemy Event を使用（`@event.listens_for(BaseModel, 'before_update')`）
  - その他DB: `onupdate=datetime.now` を優先（将来の切り替え用）
  - DB 種別の自動判定と最適な方法の選択
  - **重要**: `@event.listens_for(BaseModel, 'before_update', propagate=True)` は、すべての `BaseModel` サブクラスに自動的に適用される
- [x] `update_from_dict()` の保護強化:
  - `default_exclude_fields` に `created_at`, `updated_at` を追加
  - システムカラムがクライアントから更新されないことを保証
  - **重要**: `exclude_fields` 引数で `id`, `created_at`, `updated_at` を含めようとしても、セキュリティ上常に除外される（意図した動作）
- [x] テストで保証:
  - `id`, `created_at`, `updated_at` がユーザー側から変更不可であることを確認
  - `updated_at` が更新時に自動更新されることを確認

**実装内容**:

1. **`updated_at` の自動更新（SQLAlchemy Event）**:
   - `base_model.py` に `@event.listens_for` を追加（末尾）
   - `before_update` イベントで `updated_at` を `datetime.now()` で更新
   - `propagate=True` で全サブクラスに適用

2. **`update_from_dict()` の保護強化**:
   - `default_exclude_fields` を `{'id', 'created_at', 'updated_at'}` に変更
   - docstring を更新（セキュリティ上常に除外される旨を明記）

3. **テスト結果**:
   - `test_system_columns_protection.py`: 6/6 パス ✅
     * `test_update_from_dict_excludes_id` - id保護
     * `test_update_from_dict_excludes_created_at` - created_at保護
     * `test_update_from_dict_excludes_updated_at` - updated_at保護
     * `test_updated_at_auto_update_on_commit` - 自動更新
     * `test_created_at_not_change_on_update` - created_at不変
     * `test_all_system_columns_protected_together` - 統合テスト
   - `test_model.py`: 5/5 パス（既存機能維持） ✅

### Phase 3: info['in_response'] の実装
- [x] `_should_exclude_from_schema()` を拡張して `schema_type='response'` に対応
- [x] **`_should_exclude_from_schema()` のロジック明確化**:
  - `schema_type` パラメータ ('create', 'update', 'response') を追加
  - システムカラムは Create/Update で除外、Response で含める
  - 外部キーは `info` メタデータ優先で判定
  - 複合外部キーの検出ロジックを追加してテスト
- [x] **システムカラムのデフォルトルール**:
  - `id`, `created_at`, `updated_at`:
    - Create: ❌ 除外（自動生成/自動設定）
    - Update: ❌ 除外（変更不可）
    - Response: ✅ 含める（読み取り可能）
- [x] **外部キーのデフォルトルール（柔軟性重視）**:
  - 外部キー (`*_id`):
    - Create: ✅ 含める（デフォルト、`info={'in_create': False}` で除外可能）
    - Update: ✅ 含める（デフォルト、`info={'in_update': False}` で除外可能）
    - Response: ✅ 含める
  - **理由**: 多くのユースケースで外部キーの指定/変更が必要
  - **セキュリティ**: バリデーションと認可で対応（スキーマ除外ではない）
  - **センシティブな外部キー**（所有者など）は明示的に `info={'in_create': False, 'in_update': False}` で除外
- [x] **通常カラム**:
  - Create: ✅ 含める
  - Update: ✅ 含める
  - Response: ✅ 含める
- [x] `info={'in_response': False}` で明示的に除外されたフィールド: 除外
- [x] `@response_field` で宣言されたフィールド: 常に含める

**実装内容**:

1. **`_should_exclude_from_schema()` の拡張**:
   - `schema_type` パラメータに `'response'` を追加
   - Response の場合: `info={'in_response': False}` のみ除外
   - Create/Update の場合: システムカラムを除外、外部キーはデフォルトで含める

2. **`get_response_schema()` の更新**:
   - `_should_exclude_from_schema(col, 'response')` を使用して一貫性を確保
   - `info` で除外指定されたフィールドをスキップ

3. **テスト結果**:
   - `test_base_model_auto_response.py`: 14/14 パス ✅
     * システムカラムの Response 包含テスト
     * 外部キーの Response 包含テスト
     * `info={'in_response': False}` 除外テスト
     * `@response_field` デコレータテスト
     * Create/Update のシステムカラム除外テスト
     * 外部キーのデフォルト動作テスト
     * センシティブな外部キーの除外テスト
   - 既存テスト: 全てパス（後方互換性維持）

### Phase 4: BaseModel からの削除とカスタム型リネーム
- [ ] `BaseModel` から `@response_field` デコレータを削除
- [ ] `BaseModel` から `get_response_schema()` メソッドを削除
- [ ] `BaseModel` から `_EXTRA_FIELDS_REGISTRY` 関連コードを完全に削除（互換性不要）
- [ ] `BaseModel` から `get_extra_fields_debug()` を削除
- [ ] **`CreatedAt` カスタム型を `AutoDateTime` にリネーム**（破壊的変更）:
  - `repom/custom_types/CreatedAt.py` → `AutoDateTime.py`
  - `from repom.custom_types.CreatedAt import CreatedAt` → `from repom.custom_types.AutoDateTime import AutoDateTime`
  - すべての使用箇所を一括置換
  - mine_py プロジェクトでも一括置換を実施

### Phase 5: テスト
- [ ] 既存テストを `BaseModelAuto` 用に更新
- [ ] `info['in_response']` の新規テストを追加:
  - `in_response=True` のテスト（デフォルト）
  - `in_response=False` の除外テスト
  - システムカラム（id, created_at, updated_at）が Response に含まれることを確認
  - 外部キーが Response に含まれることを確認
- [ ] **システムカラムの保護テスト**:
  - `id`, `created_at`, `updated_at` が `update_from_dict()` で更新されないことを確認
  - `id`, `created_at`, `updated_at` が Create スキーマに含まれないことを確認
  - `id`, `created_at`, `updated_at` が Update スキーマに含まれないことを確認
  - `updated_at` が更新時に自動更新されることを確認（SQLite/その他DB）
- [ ] **外部キーのテスト**:
  - 外部キーが Create スキーマに含まれることを確認（デフォルト）
  - 外部キーが Update スキーマに含まれることを確認（デフォルト）
  - 外部キーが Response スキーマに含まれることを確認
  - `info={'in_create': False}` で外部キーが Create から除外されることを確認
  - `info={'in_update': False}` で外部キーが Update から除外されることを確認
- [ ] `@response_field` の動作テスト（BaseModelAuto で）
- [ ] 前方参照解決のテスト
- [ ] 全テストスイートの実行: `poetry run pytest tests/unit_tests`

### Phase 6: ドキュメント更新
- [x] `docs/guides/base_model_auto_guide.md` を作成:
  - BaseModelAuto の完全ガイド
  - Response スキーマ生成の説明
  - `info['in_response']` の説明
  - 使用例の追加
  - 前方参照の解決方法
  - FastAPI 統合の実装例
- [x] `docs/guides/repository_and_utilities_guide.md` を作成:
  - BaseRepository の完全ガイド
  - FilterParams と as_query_depends() の説明
  - auto_import_models の使い方
- [x] `README.md` を簡略化:
  - 1,388行から291行に圧縮
  - 詳細セクションを削除し、docs/guides/ へのリンクを追加
  - 基本的な使い方のみを記載
- [x] `.github/copilot-instructions.md` を更新:
  - 新しいガイドファイルへの参照方法を追加
  - AI エージェントが適切なガイドを参照できるように整理
- [x] `docs/technical/ai_context_management.md` を作成:
  - AI エージェントのコンテキスト管理に関する技術詳細
  - トークン消費量の最適化戦略

### Phase 7: 外部プロジェクトへの移行通知
- [ ] mine_py プロジェクトに移行依頼を出す
- [ ] 移行手順書を作成:
  - `BaseModel` → `BaseModelAuto` への変更
  - `@BaseModel.response_field` → `@BaseModelAuto.response_field` への変更
  - **`CreatedAt` → `AutoDateTime` への一括置換**
  - `get_response_schema()` の動作確認

## Testing Strategy

### 新規テストケース

```python
# tests/unit_tests/test_base_model_auto_response.py

def test_response_schema_includes_system_columns():
    """id, created_at, updated_at が Response に含まれることを確認"""
    
def test_response_schema_includes_foreign_keys():
    """外部キーが Response に含まれることを確認"""
    
def test_response_schema_excludes_with_info_flag():
    """info={'in_response': False} で除外されることを確認"""
    
def test_response_field_decorator():
    """@response_field で宣言されたフィールドが Response に含まれることを確認"""
    
def test_response_schema_forward_refs():
    """前方参照が正しく解決されることを確認"""

def test_response_schema_default_behavior():
    """info を指定しない場合のデフォルト動作を確認"""

# tests/unit_tests/test_system_columns_protection.py

def test_update_from_dict_excludes_id():
    """update_from_dict() で id が更新されないことを確認"""

def test_update_from_dict_excludes_created_at():
    """update_from_dict() で created_at が更新されないことを確認"""

def test_update_from_dict_excludes_updated_at():
    """update_from_dict() で updated_at が更新されないことを確認"""

def test_create_schema_excludes_system_columns():
    """Create スキーマに id, created_at, updated_at が含まれないことを確認"""

def test_update_schema_excludes_system_columns():
    """Update スキーマに id, created_at, updated_at が含まれないことを確認"""

def test_updated_at_auto_update_on_save():
    """save() 時に updated_at が自動更新されることを確認（SQLite）"""

def test_updated_at_auto_update_on_commit():
    """commit() 時に updated_at が自動更新されることを確認"""

def test_created_at_not_change_on_update():
    """更新時に created_at が変更されないことを確認"""

# tests/unit_tests/test_foreign_key_handling.py

def test_foreign_key_included_in_create_schema_by_default():
    """外部キーがデフォルトで Create スキーマに含まれることを確認"""

def test_foreign_key_included_in_update_schema_by_default():
    """外部キーがデフォルトで Update スキーマに含まれることを確認"""

def test_foreign_key_included_in_response_schema():
    """外部キーが Response スキーマに含まれることを確認"""

def test_foreign_key_excluded_from_create_with_info_flag():
    """info={'in_create': False} で外部キーが Create から除外されることを確認"""

def test_foreign_key_excluded_from_update_with_info_flag():
    """info={'in_update': False} で外部キーが Update から除外されることを確認"""

def test_sensitive_foreign_key_handling():
    """センシティブな外部キー（owner_id など）が適切に除外されることを確認"""

def test_composite_foreign_key_detection():
    """複合外部キーが正しく検出されることを確認
    
    例: ForeignKeyConstraint(['col1', 'col2'], ['other.col1', 'other.col2'])
    各カラムが独立して Create/Update Schema に含まれることを確認
    """
```

### 既存テストの更新

- `tests/unit_tests/test_response_field.py`: `BaseModelAuto` 用に更新
- `tests/unit_tests/test_response_schema_forward_refs.py`: `BaseModelAuto` 用に更新
- `tests/unit_tests/test_response_schema_fastapi.py`: `BaseModelAuto` 用に更新

## Breaking Changes

### 影響を受けるコード

1. **`@response_field` デコレータの廃止**:
   ```python
   # ❌ 動かなくなるコード
   from repom.base_model import BaseModel
   
   class MyModel(BaseModel):
       @BaseModel.response_field(extra=str)
       def to_dict(self):
           ...
   
   MyResponse = MyModel.get_response_schema()
   ```

2. **`CreatedAt` カスタム型の `AutoDateTime` へのリネーム**:
   ```python
   # ❌ 動かなくなるコード
   from repom.custom_types.CreatedAt import CreatedAt
   
   class MyModel(BaseModel):
       created_at = Column(CreatedAt, nullable=False)
       updated_at = Column(CreatedAt, nullable=False)
   ```

### 移行後のコード

```python
# ✅ 移行後
from repom.base_model_auto import BaseModelAuto
from repom.custom_types.AutoDateTime import AutoDateTime

class MyModel(BaseModelAuto):
    name = Column(
        String(100),
        info={
            'in_create': True,
            'in_update': True,
            'in_response': True,  # デフォルトなので省略可
            'description': '名前'
        }
    )
    
    created_at = Column(AutoDateTime, nullable=False)
    updated_at = Column(AutoDateTime, nullable=False)
    
    password_hash = Column(
        String(255),
        info={'in_response': False}  # Response から除外
    )
    
    @BaseModelAuto.response_field(extra=str)
    def to_dict(self):
        data = super().to_dict()
        data['extra'] = 'value'
        return data

MyResponse = MyModel.get_response_schema()
```

### 移行手順

1. `mine_py` プロジェクトの `@response_field` 使用箇所を特定
2. 各モデルを `BaseModel` から `BaseModelAuto` に移行
3. `response_field` を `Column` の `info` メタデータに移行
4. **すべての `CreatedAt` を `AutoDateTime` に一括置換**
5. テストを実行して動作確認
6. **注意**: `_EXTRA_FIELDS_REGISTRY` は完全に削除されるため、移行は一括で実施

## Success Criteria

- [ ] `BaseModelAuto` で Create/Update/Response の3つのスキーマを生成できる
- [ ] `info['in_response']` でフィールドの除外を制御できる
- [ ] システムカラム（id, created_at, updated_at）がデフォルトで Response に含まれる
- [ ] 外部キーがデフォルトで Response に含まれる
- [ ] `@response_field` デコレータが `BaseModelAuto` で動作する
- [ ] 前方参照が正しく解決される
- [ ] **システムカラムの保護**:
  - [ ] `id`, `created_at`, `updated_at` が Update スキーマに含まれない
  - [ ] `id`, `created_at`, `updated_at` が `update_from_dict()` で更新されない
  - [ ] `updated_at` が更新時に自動更新される（SQLite および その他DB）
- [ ] すべてのテストがパスする
- [ ] ドキュメントが更新されている
- [ ] 外部プロジェクト（mine_py）への移行通知が完了している

## Related Documents

- **実装ガイド**: `docs/base_model_auto_guide.md`
- **技術詳細**: `docs/technical/get_response_schema_technical.md`
- **前方参照調査**: `docs/research/auto_forward_refs_resolution.md`
- **Issue #1**: `docs/issue/completed/001_get_response_schema_forward_refs_improvement.md`
- **Issue #2**: `docs/issue/completed/002_sqlalchemy_column_inheritance_constraint.md`

## Notes

### 設計上の考慮事項

1. **`@response_field` の位置づけ**:
   - Column 定義だけでは表現できない計算フィールドやリレーションシップフィールドを宣言
   - `info` パラメータとは独立した機能として維持

2. **`info['in_response']` の優先度**:
   - 明示的に `False` を指定した場合は常に除外
   - 指定がない場合はデフォルト動作（含める）

3. **システムカラムの自動更新と保護**:
   - `updated_at` は DB レベルで自動更新（SQLAlchemy Event 使用）
   - SQLite と その他DB で自動的に最適な方法を選択（将来の拡張性）
   - `id`, `created_at`, `updated_at` はクライアントから更新不可
   - Update スキーマから自動的に除外
   - Response スキーマには含める（読み取りは可能）
   - **重要**: `update_from_dict()` の `exclude_fields` 引数で `id`, `created_at`, `updated_at` を含めようとしても、セキュリティ上常に除外される（意図した動作）

4. **後方互換性**:
   - 今回は破壊的変更を許容
   - 将来的には `BaseModel` に deprecated 警告を追加する方式も検討可能

5. **パフォーマンス**:
   - スキーマキャッシュは維持
   - グローバルレジストリは `BaseModelAuto` で管理

### `updated_at` 自動更新の実装詳細

#### SQLAlchemy Event による実装（推奨）
```python
from sqlalchemy import event
from datetime import datetime

@event.listens_for(BaseModel, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    """更新前に updated_at を自動設定"""
    if hasattr(target, 'updated_at'):
        target.updated_at = datetime.now()
```

**理由**:
- SQLite でも確実に動作
- すべての DB で統一的に動作
- シンプルで理解しやすい
- 将来的に `onupdate=datetime.now` に切り替え可能（DB判定ロジックを追加）
- **重要**: `@event.listens_for(BaseModel, 'before_update', propagate=True)` は、すべての `BaseModel` サブクラスに自動的に適用される

#### 将来の拡張（オプション）
```python
def _setup_updated_at_auto_update(cls):
    """DB種別に応じて最適な updated_at 自動更新を設定"""
    db_type = get_db_type()  # 'sqlite', 'postgresql', 'mysql', etc.
    
    if db_type == 'sqlite':
        # SQLite: Event を使用
        @event.listens_for(cls, 'before_update', propagate=True)
        def receive_before_update(mapper, connection, target):
            if hasattr(target, 'updated_at'):
                target.updated_at = datetime.now()
    else:
        # その他DB: onupdate を使用（DB側で自動更新）
        cls.updated_at = Column(CreatedAt, onupdate=datetime.now)
```

### システムカラムの除外ルール

| カラム | Create | Update | Response | 備考 |
|--------|--------|--------|----------|------|
| `id` | ❌ 除外 | ❌ 除外 | ✅ 含める | 自動生成、主キー |
| `created_at` | ❌ 除外 | ❌ 除外 | ✅ 含める | 自動設定、不変 |
| `updated_at` | ❌ 除外 | ❌ 除外 | ✅ 含める | 自動更新 |
| **外部キー** | ✅ 含める | ✅ 含める | ✅ 含める | リレーション指定/変更 |
| 通常カラム | ✅ 含める | ✅ 含める | ✅ 含める | ユーザーデータ |

### 外部キーのセキュリティ対策

#### 1. バリデーション（Validator Mixin）
```python
class PostValidatorMixin:
    @field_validator('category_id')
    def validate_category(cls, v):
        # カテゴリが存在するか確認
        if not CategoryRepository().get_by_id(v):
            raise ValueError('Category not found')
        return v
```

#### 2. 認可チェック（FastAPI エンドポイント）
```python
@app.post("/posts/")
def create_post(post: PostCreate, current_user: User = Depends(get_current_user)):
    # 所有者を自動設定（クライアントからは受け取らない）
    post_data = post.dict()
    post_data['owner_id'] = current_user.id
    
    # カテゴリへのアクセス権を確認
    if not has_access_to_category(current_user, post_data['category_id']):
        raise HTTPException(403, "Access denied")
    
    return PostRepository().dict_save(post_data)
```

#### 3. 監査ログ
```python
if old_category_id != new_category_id:
    audit_log.record("category_changed", user_id, post_id, old_category_id, new_category_id)
```

### 外部キーの設計パターン

#### パターンA: 通常の外部キー（変更可能）
```python
category_id = Column(
    Integer,
    ForeignKey('categories.id'),
    info={
        'in_create': True,   # ✅ 作成時に指定
        'in_update': True,   # ✅ 更新時に変更可能
        'in_response': True, # ✅ Response に含める
        'description': 'カテゴリID'
    }
)
```

#### パターンB: センシティブな外部キー（変更不可）
```python
owner_id = Column(
    Integer,
    ForeignKey('users.id'),
    info={
        'in_create': False,  # ❌ 認証から自動設定
        'in_update': False,  # ❌ 所有者変更は別エンドポイント
        'in_response': True, # ✅ 読み取りは可能
        'description': '所有者ID（システム設定）'
    }
)
```

#### パターンC: リードオンリーの外部キー（参照のみ）
```python
created_by_id = Column(
    Integer,
    ForeignKey('users.id'),
    info={
        'in_create': False,  # ❌ 認証から自動設定
        'in_update': False,  # ❌ 作成者は変更不可
        'in_response': True, # ✅ 読み取りは可能
        'description': '作成者ID'
    }
)
```

### 将来の改善案

- `@response_field` をクラスデコレータとして使えるようにする
- より柔軟なデコレータ呼び出し（例: `@response_field` だけで動作）
- Response スキーマのバリデーター Mixin サポート
- OpenAPI 統合の強化

---

**作成日**: 2025-11-14  
**最終更新**: 2025-11-14  
**担当**: AI Agent + User

---

## Appendix: システムカラムと外部キーの設計メモ

### システムカラムの保護に関する設計

#### 問題の背景
現在、`update_from_dict()` では `id` のみが除外されており、`created_at` と `updated_at` はクライアントから更新可能な状態です。これはセキュリティとデータ整合性の観点から問題があります。

#### 解決策
1. **`update_from_dict()` の強化**:
   ```python
   default_exclude_fields = {'id', 'created_at', 'updated_at'}
   ```

2. **Create/Update スキーマからの自動除外**:
   ```python
   # BaseModelAuto._should_exclude_from_schema()
   if schema_type in ('create', 'update'):
       if col.name in {'id', 'created_at', 'updated_at'}:
           return True  # 除外
   ```

3. **`updated_at` の自動更新**:
   - SQLAlchemy Event を使用して確実に動作
   - すべてのDB（SQLite含む）で統一的に動作

#### テストで保証すべき項目
- ✅ `id` がクライアントから変更不可（Create/Update）
- ✅ `created_at` がクライアントから変更不可（Create/Update）
- ✅ `updated_at` がクライアントから変更不可（Create/Update）
- ✅ `updated_at` が更新時に自動更新される
- ✅ Create スキーマにシステムカラムが含まれない
- ✅ Update スキーマにシステムカラムが含まれない
- ✅ Response スキーマにシステムカラムが含まれる（読み取り可能）

### 外部キーの設計に関する方針

#### 業界標準の調査結果

**主要 API の挙動**:
- **GitHub API**: Create/Update で外部キーを受け取る
- **Stripe API**: Create で外部キー必須、Update で一部変更可能
- **Twitter API**: Create で外部キー受け取る

**結論**: 外部キーを Create/Update に含めるのが標準的

#### repom での設計方針

**デフォルト**: 外部キーは Create/Update に含める（柔軟性重視）

**理由**:
1. **柔軟性**: リソース作成時に関連を指定、更新時に関連を変更できる
2. **標準的**: 他の API フレームワーク（Django REST, FastAPI）も同様
3. **セキュリティ**: バリデーションと認可で対応（スキーマ除外ではない）

**セキュリティ対策**:
- バリデーション: 外部キーが存在するか確認
- 認可チェック: ユーザーが指定した関連リソースへのアクセス権を確認
- 監査ログ: 外部キーの変更を記録

**センシティブな外部キーは明示的に除外**:
```python
owner_id = Column(
    Integer,
    ForeignKey('users.id'),
    info={
        'in_create': False,  # 認証から自動設定
        'in_update': False   # 所有者変更は別エンドポイント
    }
)
```

#### 外部キーの設計パターン

1. **通常の外部キー**: 作成・変更可能（`in_create=True`, `in_update=True`）
   - 例: `category_id`, `department_id`

2. **センシティブな外部キー**: システム設定、変更不可（`in_create=False`, `in_update=False`）
   - 例: `owner_id`, `tenant_id`

3. **リードオンリーの外部キー**: 参照のみ（`in_create=False`, `in_update=False`）
   - 例: `created_by_id`, `approved_by_id`

#### テストで保証すべき項目
- ✅ 外部キーがデフォルトで Create スキーマに含まれる
- ✅ 外部キーがデフォルトで Update スキーマに含まれる
- ✅ 外部キーが Response スキーマに含まれる
- ✅ `info={'in_create': False}` で Create から除外される
- ✅ `info={'in_update': False}` で Update から除外される
- ✅ センシティブな外部キーが適切に保護される
- ✅ 複合外部キー（`ForeignKeyConstraint`）が正しく検出される

### CreatedAt カスタム型の AutoDateTime へのリネーム

#### 問題の背景
現在の `CreatedAt` という名前は、`created_at` カラム専用のように見えますが、実際には `updated_at` カラムにも使われています。これは命名が目的を正確に表現できていません。

#### 解決策: AutoDateTime へのリネーム（破壊的変更）

**理由**:
1. **命名の明確化**: `CreatedAt` という名前は `created_at` 専用に見えるが、実際には `updated_at` にも使われている
2. **汎用性の表現**: `AutoDateTime` という名前の方が「自動的に日時を設定する型」という目的が明確
3. **一貫性**: 一度の破壊的変更で、将来にわたって混乱を避けられる

**移行方法**:
- `repom/custom_types/CreatedAt.py` → `AutoDateTime.py`
- すべての `from repom.custom_types.CreatedAt import CreatedAt` を `from repom.custom_types.AutoDateTime import AutoDateTime` に一括置換
- mine_py プロジェクトでも一括置換を実施

**影響範囲**:
- 破壊的変更だが、一括置換で容易に移行可能
- 命名の改善により、将来の開発者が混乱しなくなる
