# 柔軟な auto_import_models 設定

## ステータス
- **段階**: 完了
- **優先度**: 中
- **複雑度**: 低
- **作成日**: 2025-11-15
- **完了日**: 2025-11-15

## 概要

設定ファイルで複数のモデルディレクトリを指定できるようにし、`models/__init__.py` への手動記述を不要にする。これにより、Alembic マイグレーションと db コマンドでのモデル認識ミスを防ぐ。

## モチベーション

### `auto_import_models` の役割と重要性

`auto_import_models` は repom において**極めて重要な機能**です。この機能がないと、以下のコマンドが正常に動作しません：

| コマンド | 目的 | auto_import_models がないとどうなるか |
|---------|------|----------------------------------|
| `poetry run alembic revision --autogenerate` | マイグレーションファイル生成 | ❌ **空のマイグレーションファイルが生成される**（モデルが認識されない） |
| `poetry run alembic upgrade head` | マイグレーション適用 | ❌ テーブルが作成/更新されない |
| `poetry run db_create` | データベース作成 | ❌ **テーブルが作成されない**（エラーも出ない） |
| `poetry run db_delete` | データベース削除 | ❌ **テーブルが削除されない**（エラーも出ない） |
| `poetry run db_create_master` | 初期データ挿入 | ❌ モデルにアクセスできない |

### 動作の仕組み

```
1. models/__init__.py で auto_import_models() を呼び出す
   ↓
2. load_models() 関数が models パッケージをインポート
   ↓
3. load_set_model_hook_function() が load_models() を実行
   ↓
4. 各種コマンドと Alembic が Base.metadata にアクセス
   ↓
5. すべてのモデルが SQLAlchemy に登録される
```

**重要**: `Base.metadata` にモデルが登録されていないと、SQLAlchemy はそのモデルの存在を認識できません。

### 現在の問題

**現状の使い方**:
```python
# models/__init__.py で直接呼び出す（必須）
from pathlib import Path
from repom.utility import auto_import_models

auto_import_models(
    models_dir=Path(__file__).parent,
    base_package='myapp.models'
)
```

**問題点**:
1. **手動設定が必須で忘れやすい**
   - 各プロジェクトで `models/__init__.py` に記述が必要
   - **記述を忘れると、エラーなしで動作がおかしくなる**
   - Alembic: 空のマイグレーションファイルが生成される
   - db_create: テーブルが作成されない（エラーなし）

2. **単一ディレクトリのみサポート**
   - 複数の models ディレクトリがある場合、それぞれで呼び出しが必要
   - モノレポ構成で共有モデルと個別モデルを扱いにくい

3. **エラーが分かりにくい**
   - モデルが登録されていない場合、サイレントに失敗する
   - デバッグが困難

4. **柔軟性の欠如**
   - 動的にモデルディレクトリを追加できない
   - 環境によってモデルのロード元を変更できない

### 実際のエラーケース

```bash
# ❌ models/__init__.py に auto_import_models を記述し忘れた場合

# マイグレーションファイル生成
poetry run alembic revision --autogenerate -m "add user model"
# → 空のマイグレーションファイルが生成される（モデルが認識されない）

# データベース作成
poetry run db_create
# → 成功メッセージは出るが、テーブルが作成されない

# エラーメッセージが出ないため、問題に気づきにくい
```

### 理想の動作

**設定ベース**:
```python
# config.py または環境変数で指定
CONFIG.MODEL_LOCATIONS = ['myapp.models', 'shared.models']

# models/__init__.py への記述不要
# すべてのコマンドで自動認識される
poetry run alembic revision --autogenerate -m "sync"
poetry run db_create
```

**利点**:
- models/__init__.py への記述不要（設定ミスを防ぐ）
- 複数ディレクトリを一括指定
- 環境ごとに異なるモデルセットをロード可能

## ユースケース

### 1. モノレポ構成
複数の models ディレクトリを一括管理：
```python
CONFIG.MODEL_LOCATIONS = ['shared.models', 'api.models', 'admin.models']
```

### 2. プラグインモデル
動的にモデルを追加：
```python
CONFIG.MODEL_LOCATIONS = ['myapp.models']
if CONFIG.ENABLE_PAYMENT:
    CONFIG.MODEL_LOCATIONS.append('plugins.payment.models')
```

### 3. テスト環境
環境別にモデルを切り替え：
```python
if CONFIG.EXEC_ENV == 'test':
    CONFIG.MODEL_LOCATIONS.append('tests.fixtures.models')
```

### 4. 段階的マイグレーション
新旧モデルの並行運用：
```python
CONFIG.MODEL_LOCATIONS = ['myapp.models.legacy', 'myapp.models.v2']
```

### 5. 設定忘れ防止
現在の問題を解決：
```python
# ❌ 現状: models/__init__.py に書き忘れ → エラーなしで失敗
# ✅ 理想: 設定ファイルで一元管理 → 忘れない
```

## 推奨アプローチ

### 既存の統合機構を活用

**方針**: `load_models()` 関数を修正するだけで全体に反映される。

**理由**:
- すべてのコマンドが `load_set_model_hook_function()` を使用
- alembic/env.py も db_create/db_delete も変更不要
- 後方互換性を維持しやすい

**概念**:
```python
# repom/config.py の load_models() を修正
def load_models():
    if config.MODEL_LOCATIONS:
        # 新機能: 複数パッケージ対応
        auto_import_models_from_list(config.MODEL_LOCATIONS)
    else:
        # 既存動作（後方互換性）
        from repom import models
```

**必要な新機能**:
1. `auto_import_models_by_package(package_name)` - パッケージ名からモデルをインポート
2. `auto_import_models_from_list(package_names)` - 複数パッケージを一括インポート
3. `MineDbConfig.MODEL_LOCATIONS` - 設定プロパティ
4. `MineDbConfig.MODEL_EXCLUDED_DIRS` - 除外ディレクトリ

**技術的考慮事項**:
- パッケージ解決: `importlib.import_module()` で __path__ を取得
- エラーハンドリング: 警告を出して継続（fail_on_error=False）
- 重複防止: Python の import キャッシュを活用
- インポート順序: アルファベット順（既存と同じ）

## 統合ポイント

### 影響を受けるコンポーネント
- `repom/utility.py` - `auto_import_models_by_package`, `auto_import_models_from_list` 関数の追加
- `repom/config.py` - `MODEL_LOCATIONS`, `MODEL_EXCLUDED_DIRS` プロパティ追加、`load_models()` 修正
- `repom/scripts/*` - 変更不要（既存の `load_set_model_hook_function()` を使用）
- `alembic/env.py` - 変更不要（既存の `load_set_model_hook_function()` を使用）
- `README.md`, `docs/guides/` - ドキュメント更新

### 既存機能との相互作用
- 既存の `auto_import_models` 関数は維持（後方互換性）
- 既存の `load_set_model_hook_function()` 機構を活用
- `config.set_models_hook` に登録された `load_models()` を修正するだけ

### 統合の利点
- すべてのコマンド（db_create, db_delete, alembic など）は変更不要
- 1 箇所（`load_models()` 関数）の修正で全体に反映
- 後方互換性を維持

## 次のステップ

### 実装優先順位

#### Phase 1: 基本機能（高優先度）
- ✅ `auto_import_models_by_package` 関数の実装
- ✅ `auto_import_models_from_list` 関数の実装
- ✅ `MineDbConfig` への `MODEL_LOCATIONS` 追加
- ✅ `load_models()` 関数の修正（MODEL_LOCATIONS 対応）
- ✅ 単体テストの作成（31テスト、すべて成功）

#### Phase 1.5: 設定制御機能（完了 - 2025-11-15）
- ✅ `MineDbConfig` への `model_import_strict` 追加
- ✅ `load_models()` での `fail_on_error` パラメータ連携
- ✅ 単体テストの追加（4テスト追加）
- ✅ ドキュメント更新（ガイドと Issue）

#### Phase 2: 統合とドキュメント（未実装 - 実際の使用で検証予定）
- [ ] 統合テスト（実際のプロジェクト構造での検証）
- [ ] README.md の更新
- [ ] 使用例の追加

#### Phase 3: 高度な機能（未実装 - 将来の必要性に応じて検討）
- [ ] プリセット設定機能
- [ ] デバッグモード
- [ ] インポート統計機能

### 検証項目（Phase 1.5 完了時点で達成）

- ✅ 既存の `models/__init__.py` を使用しているプロジェクトが動作すること（後方互換性）
  - テスト: `test_load_models_backward_compatibility_no_model_locations`
- ✅ model_locations を設定したプロジェクトが正常に動作すること
  - テスト: `test_load_models_with_config_locations`
- ✅ 複数のモデルディレクトリが正しくインポートされること
  - テスト: `test_auto_import_models_from_list_multiple_packages`
- ✅ インポート失敗時に適切な動作をすること（警告 or エラー）
  - テスト: `test_auto_import_models_from_list_fail_on_error_false/true`
- ✅ セキュリティ検証が正しく機能すること
  - テスト: `test_security_validation_*` (6テスト)
- ✅ Strict モードが正しく機能すること
  - テスト: `test_load_models_strict_mode_*` (3テスト)

### 実装決定事項（最終版）

1. **設定方法**: Python コード（CONFIG_HOOK 経由）
2. **インポート失敗時の動作**: デフォルトで警告のみ（`model_import_strict` で制御可能）
3. **キャッシュ**: Python の import キャッシュを利用
4. **モデルのインポート順序**: アルファベット順
5. **後方互換性**: 既存の動作を維持（`model_locations=None` で従来通り）
6. **セキュリティ検証スキップ**: `allowed_prefixes=None` で可能（直接呼び出し時のみ、`load_models()` では常に検証）

### 実装完了後の使用例（最終版）

#### 親プロジェクトでの CONFIG_HOOK 設定

```python
# parent_project/config.py
from repom.config_hook import CONFIG_HOOK

def configure_repom():
    CONFIG_HOOK.config.model_locations = ['parent_project.models']
    CONFIG_HOOK.config.model_excluded_dirs = {'__pycache__', 'migrations'}
    CONFIG_HOOK.config.allowed_package_prefixes = {'parent_project.', 'repom.'}
    CONFIG_HOOK.config.model_import_strict = False  # デフォルト: 警告のみ

configure_repom()
```

#### 直接呼び出しの例

```python
from repom.utility import auto_import_models_by_package

# セキュリティ検証あり
auto_import_models_by_package(
    'parent_project.models',
    excluded_dirs={'__pycache__'},
    allowed_prefixes={'parent_project.', 'repom.'}
)
```

## 解決済みの実装決定（Phase 1.5 完了時点）

1. ✅ **設定方法**: Python コード（CONFIG_HOOK 経由）のみサポート
2. ✅ **インポート失敗時**: デフォルトで警告のみ（`model_import_strict=False`）
3. ✅ **キャッシュ**: Python の import キャッシュで十分
4. ✅ **インポート順序**: アルファベット順（既存 `auto_import_models` と同じ）
5. ✅ **後方互換性**: `model_locations=None` なら従来通り `models/__init__.py` を使用
6. ✅ **セキュリティ**: `allowed_package_prefixes` による検証（デフォルト: `{'repom.'}`）
7. ✅ **セキュリティスキップ**: `allowed_prefixes=None` は直接呼び出しのみ許可
8. ✅ **存在しないパッケージ**: `model_import_strict` で制御（デフォルト: 警告のみ）

未実装（Phase 2以降で検討）:
- プラグインモデルの動的追加
- エラーメッセージの詳細化（トラブルシューティングガイド）

## テスト結果と発見事項

### Phase 1 実装完了（2025-11-15）

**実装内容**:
- ✅ `auto_import_models_by_package()` 関数（セキュリティ検証付き）
- ✅ `auto_import_models_from_list()` 関数（バッチインポート）
- ✅ `MineDbConfig` プロパティ（model_locations, model_excluded_dirs, allowed_package_prefixes）
- ✅ `load_models()` 修正（設定ベース対応）
- ✅ 単体テスト 27個（すべて成功）
- ✅ ガイドドキュメント作成（`docs/guides/auto_import_models_guide.md`）

### Phase 1.5 実装完了（2025-11-15）

**実装内容**:
- ✅ `MineDbConfig` への `model_import_strict` プロパティ追加
- ✅ `load_models()` での `fail_on_error` パラメータ連携
- ✅ 単体テスト 4個追加（合計31テスト）
- ✅ ドキュメント更新（ガイドと Issue）

**テストで発見された重要な動作**:

#### 1. セキュリティチェックとImportErrorの優先順位

**動作**: セキュリティチェックが ImportError より先に実行される

```python
auto_import_models_by_package(
    'nonexistent.models',  # 存在しない
    allowed_prefixes={'trusted.'}  # 許可されていない
)
# → ValueError: Security（ImportErrorより先）
```

**決定**: ✅ セキュリティチェックを最優先（現在の実装を維持）
**理由**: 存在しないパッケージでも、許可されていなければ即座に拒否すべき


#### 2. 存在しないパッケージが許可リストにある場合

**現在の動作**:
```python
# fail_on_error=False（デフォルト）
auto_import_models_from_list(
    package_names=['nonexistent.models'],
    allowed_prefixes={'nonexistent.'},
    fail_on_error=False
)
# → 警告メッセージを出力して継続

# fail_on_error=True
auto_import_models_from_list(
    package_names=['nonexistent.models'],
    allowed_prefixes={'nonexistent.'},
    fail_on_error=True
)
# → ImportError を発生
```

**Phase 1.5 での決定**: 
- ✅ **採用**: 案C - 設定で制御（`model_import_strict` プロパティ）
- **理由**: 
  - 開発環境ではタイポに気づきやすい（strict=True）
  - 本番環境では警告のみで継続（strict=False、デフォルト）
  - ユーザーが環境に応じて選択可能

#### 3. allowed_prefixes=None の扱い（セキュリティスキップ）

**Phase 1 での決定**:
- ✅ **採用**: 案A - None を許可（ただし直接呼び出し時のみ）
- **理由**: テスト環境などで柔軟性が必要
- **制約**: `load_models()` では常に `config.allowed_package_prefixes` を使用

```python
# 直接呼び出し: セキュリティスキップ可能
auto_import_models_by_package('test_package.models', allowed_prefixes=None)

# load_models() 経由: 常にセキュリティ検証
CONFIG_HOOK.config.model_locations = ['myapp.models']
load_models()  # allowed_package_prefixes が自動適用
```

---

## Phase 2以降の検討事項（未実装）

以下の機能は Phase 1/1.5 では実装せず、将来的に必要性が確認された場合に検討します。

### 1. エラーメッセージの詳細化

**現在**: シンプルなエラーメッセージ
**改善案**: トラブルシューティングガイドを含む詳細なメッセージ

理由: 現状のシンプルなメッセージで十分、複雑化は避ける

### 2. プラグインモデルの動的追加

**現在**: 静的な `model_locations` 設定のみ
**改善案**: 実行時にモデルを追加できる機能

理由: 初期実装では不要、将来のニーズに応じて検討

### 3. 統合テスト

**現在**: 31個の単体テスト
**改善案**: 実際のプロジェクト構造を模した統合テスト

理由: 単体テストで十分にカバー、統合テストは実際の使用で検証

---

## 最終実装状態（Phase 1.5 完了）

### 実装済み機能

#### repom/utility.py
```python
def auto_import_models_by_package(
    package_name: str,
    excluded_dirs: Optional[Set[str]] = None,
    allowed_prefixes: Optional[Set[str]] = None
) -> None:
    """パッケージ名からモデルをインポート（セキュリティ検証付き）"""
    
def auto_import_models_from_list(
    package_names: List[str],
    excluded_dirs: Optional[Set[str]] = None,
    allowed_prefixes: Optional[Set[str]] = None,
    fail_on_error: bool = False
) -> None:
    """複数パッケージのバッチインポート"""
```

#### repom/config.py
```python
@property
def model_locations(self) -> Optional[List[str]]:
    """モデルをインポートするパッケージ名のリスト"""
    
@property
def model_excluded_dirs(self) -> Optional[Set[str]]:
    """除外するディレクトリのセット"""
    
@property
def allowed_package_prefixes(self) -> Set[str]:
    """セキュリティ: 許可するパッケージプレフィックス（デフォルト: {'repom.'}）"""
    
@property
def model_import_strict(self) -> bool:
    """モデルインポート失敗時の動作（デフォルト: False = 警告のみ）"""
    
def load_models(self) -> None:
    """設定に基づいてモデルをインポート"""
```

### テストカバレッジ

- **合計**: 31テスト（すべて成功）
- **セキュリティ**: 6テスト
- **パッケージインポート**: 4テスト
- **Config プロパティ**: 8テスト
- **load_models 統合**: 4テスト
- **エラーハンドリング**: 3テスト
- **実世界シナリオ**: 3テスト
- **Strict モード**: 3テスト

### ドキュメント

- ✅ `docs/guides/auto_import_models_guide.md` - 使用ガイド（日本語、AI向け80%）
- ✅ `docs/issue/in_progress/004_flexible_auto_import_models.md` - 技術仕様と実装記録

---

## 完了条件（すべて達成）

- ✅ `auto_import_models_by_package()` 実装
- ✅ `auto_import_models_from_list()` 実装
- ✅ セキュリティ検証（`allowed_package_prefixes`）
- ✅ Config プロパティ（model_locations, model_excluded_dirs, allowed_package_prefixes, model_import_strict）
- ✅ `load_models()` 修正
- ✅ 単体テスト 31個（100% pass）
- ✅ ガイドドキュメント作成
- ✅ 後方互換性確認
- ✅ Strict モード実装

---

## 参考資料

- **実装ファイル**:
  - `repom/utility.py` (行243)
  - `repom/config.py` (行204)
  - `tests/unit_tests/test_auto_import_models.py` (行368, 31テスト)
  
- **ドキュメント**:
  - `docs/guides/auto_import_models_guide.md` - 詳細な使用ガイド
  - `docs/ideas/flexible_auto_import_models.md` - 元のアイディア（280行に削減）
- ✅ 柔軟性が高い（特殊なケースで使用可能）
- ✅ `load_models()` では必ず検証される（通常の使用では安全）
- ⚠️ ドキュメントで注意喚起

#### 3. エラーメッセージ改善

**決定**: 実装しない

**理由**:
- パッケージの肥大化を防ぐ
- シンプルなエラーメッセージで十分
- ドキュメントに基本的なトラブルシューティングを記載

---

## Phase 1.5 完了（2025-11-15）

### 実装内容

1. **`model_import_strict` プロパティ追加**
   - デフォルト: `False`（警告のみ）
   - `load_models()` で `fail_on_error` パラメータに渡される

2. **テスト追加**（31テスト → すべて成功）
   - `test_model_import_strict_default_is_false`
   - `test_model_import_strict_setter_and_getter`
   - `test_load_models_uses_model_import_strict`
   - `test_load_models_default_strict_false`

3. **ドキュメント更新**
   - `docs/guides/auto_import_models_guide.md`
     - `model_import_strict` プロパティの説明
     - セキュリティ検証スキップの注意事項
     - 環境別設定の例

---

## 今後の予定

### Phase 2: 統合とドキュメント（オプション）

- [ ] 統合テストの作成（実際のプロジェクトでの動作確認）
- [ ] README.md の更新（新機能の簡単な紹介）
- [ ] 使用例の追加

### Phase 3: 高度な機能（将来的に検討）

1. **設定検証コマンド**
   ```bash
   poetry run validate_models_config
   # → すべてのパッケージが存在するかチェック
   ```

2. **デバッグモード**
   ```python
   config.model_import_debug = True
   # → インポートの詳細ログを出力
   ```

3. **統計情報**
   ```python
   stats = auto_import_models_from_list_with_stats(...)
   # → {'imported': 5, 'failed': 1, 'skipped': 2}
   ```

---

## 実装方針の決定

### 今すぐ実装する変更（Phase 1.5）

なし（現在の実装で十分機能している）

### Phase 2 で実装する改善

1. **エラーメッセージの改善**
   - SecurityError: 解決策を提示
   - ImportError: トラブルシューティングガイド

2. **設定プロパティの追加**（オプション）
   - `model_import_strict: bool` - エラー時の厳格モード

3. **ドキュメントの更新**
   - エラーメッセージのパターン
   - トラブルシューティングガイド

### Phase 3 で検討する機能

1. **設定検証コマンド**
   ```bash
   poetry run validate_models_config
   # → すべてのパッケージが存在するかチェック
   ```

2. **デバッグモード**
   ```python
   config.model_import_debug = True
   # → インポートの詳細ログを出力
   ```

3. **統計情報**
   ```python
   stats = auto_import_models_from_list_with_stats(...)
   # → {'imported': 5, 'failed': 1, 'skipped': 2}
   ```

---

## 関連ドキュメント

- `repom/utility.py` - 既存の `auto_import_models` 関数
- `repom/config.py` - 設定クラスと `load_models()`
- `alembic/env.py` - Alembic 実行環境
- `docs/guides/auto_import_models_guide.md` - 使用ガイド（AI向け80%）
- `tests/unit_tests/test_auto_import_models.py` - 単体テスト（27テスト）
