# 柔軟な auto_import_models 設定

## ステータス
- **段階**: アイディア
- **優先度**: 中
- **複雑度**: 低
- **作成日**: 2025-11-15
- **最終更新**: 2025-11-15

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
- [ ] `auto_import_models_by_package` 関数の実装
- [ ] `auto_import_models_from_list` 関数の実装
- [ ] `MineDbConfig` への `MODEL_LOCATIONS` 追加
- [ ] `load_models()` 関数の修正（MODEL_LOCATIONS 対応）
- [ ] 単体テストの作成

#### Phase 2: 統合とドキュメント（中優先度）
- [ ] 統合テストの作成（複数パッケージ）
- [ ] エラーハンドリングのテスト
- [ ] README.md の更新
- [ ] `docs/guides/repository_and_utilities_guide.md` の更新
- [ ] 使用例の追加

#### Phase 3: 高度な機能（低優先度）
- [ ] プリセット設定機能
- [ ] デバッグモード
- [ ] インポート統計機能
- [ ] 条件付きインポートのサポート

### 検証項目

- [ ] 既存の `models/__init__.py` を使用しているプロジェクトが動作すること（後方互換性）
- [ ] MODEL_LOCATIONS を設定したプロジェクトが正常に動作すること
- [ ] `poetry run db_create` でテーブルが作成されること
- [ ] `poetry run alembic revision --autogenerate` でマイグレーションが生成されること
- [ ] 複数のモデルディレクトリが正しくインポートされること
- [ ] インポート失敗時に適切なエラーメッセージが表示されること

### 実装決定事項

1. **環境変数 vs Python コード**: 両方サポート（環境変数が優先）
2. **インポート失敗時の動作**: 警告を出すがプログラムは継続（`fail_on_error=False`）
3. **キャッシュ**: Python の import キャッシュを利用（重複インポート防止）
4. **モデルのインポート順序**: アルファベット順（`auto_import_models` と同じ）
5. **後方互換性**: 既存の `auto_import_models` は維持

### 実装完了後の使用例

```python
# consuming project の config.py
from repom.config import config

# 方法1: Python コードで設定
config.MODEL_LOCATIONS = [
    'myapp.models',
    'shared.models',
]

# 方法2: 環境変数で設定（優先される）
# export MODEL_LOCATIONS="myapp.models,shared.models"

# 以降、すべてのコマンドで自動的にモデルがロードされる
# poetry run db_create
# poetry run alembic revision --autogenerate -m "sync"
```

## 解決すべき質問

1. ✅ 環境変数 vs Python コード: 両方サポート、環境変数が優先
2. ✅ インポート失敗時: 警告のみ（fail_on_error=False）
3. ✅ キャッシュ: Python の import キャッシュで十分
4. ✅ インポート順序: アルファベット順（既存と同じ）
5. ❓ プラグインモデルの動的追加: 初期実装では静的、将来検討
6. ❓ パッケージ不在時: 警告してスキップ
7. ✅ テスト環境: EXEC_ENV で MODEL_LOCATIONS を変更
8. ✅ models/__init__.py との共存: MODEL_LOCATIONS 未設定なら従来通り
9. ❓ 複数プロジェクト: CONFIG_HOOK 経由でオーバーライド
10. ✅ load_set_model_hook_function: load_models() 修正のみ

## 関連ドキュメント

- `repom/utility.py` - 既存の `auto_import_models` 関数
- `repom/config.py` - 設定クラスと `load_models()`
- `alembic/env.py` - Alembic 実行環境
- `docs/guides/repository_and_utilities_guide.md` - auto_import_models ガイド
