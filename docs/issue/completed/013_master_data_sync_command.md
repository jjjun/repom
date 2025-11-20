# Issue #013: マスターデータ同期コマンドの追加

**ステータス**: ✅ 完了

**作成日**: 2025-11-19

**完了日**: 2025-11-19

**優先度**: 中

## 問題の説明

現状、マスターデータは Alembic のマイグレーションファイルに記述していますが、開発中にマイグレーションの不整合が発生し、初期化することが多いため、マスターデータも失われてしまう問題があります。

マイグレーションシステムとは独立してマスターデータを管理・投入できる仕組みが必要です。

## 提案される解決策

**`db_sync_master`** コマンドを追加し、Python ファイルで定義されたマスターデータを DB に同期する機能を実装します。

### 基本仕様

1. **Upsert のみ**: INSERT または UPDATE（DELETE は行わない）
2. **バリデーション不要**: エラーは自然に発生させる（SQL エラー）
3. **トランザクション管理**: `repom.session.transaction()` を使用
4. **データ保存**: `BaseRepository.save()` を使用（内部で `session.merge()` を使用）

### マスターデータファイルの形式

```python
# data/master/001_roles.py
from repom.models import Role  # モデルクラスをインポート

MODEL_CLASS = Role  # どのモデルか指定

MASTER_DATA = [
    {"id": 1, "name": "admin", "description": "Administrator"},
    {"id": 2, "name": "user", "description": "Regular User"},
]
```

- ファイル名はプレフィックス付き（`001_`, `002_` など）でソート順序を制御可能
- 外部キー制約は当面考慮しない（必要になったら拡張）

### 設定追加

```python
# repom/config.py
class MineDbConfig:
    master_data_dir: str = "data/master"  # マスターデータディレクトリ
```

### コマンド実行

```bash
# 基本実行
poetry run db_sync_master

# 環境指定（EXEC_ENV に従う）
EXEC_ENV=dev poetry run db_sync_master
```

## 影響範囲

### 新規作成ファイル
- `repom/scripts/db_sync_master.py` - CLI コマンドスクリプト
- `data_master/` - マスターデータ格納ディレクトリ（サンプル含む）

### 変更ファイル
- `repom/config.py` - `master_data_dir` 設定追加
- `pyproject.toml` - `db_sync_master` コマンド登録

### テストファイル
- `tests/unit_tests/test_db_sync_master.py` - 同期ロジックのテスト

## 実装計画

### Phase 1: 基本機能実装

1. **config.py に設定追加**
   - `master_data_dir` プロパティを追加

2. **db_sync_master.py スクリプト作成**
   - マスターデータファイルの読み込み（`*.py` ファイルをソート順に読む）
   - `MODEL_CLASS` と `MASTER_DATA` の抽出
   - `transaction()` 内で Upsert 処理
   - `BaseRepository.save()` を使用（内部で `merge()` 実行）

3. **pyproject.toml にコマンド登録**
   ```toml
   [tool.poetry.scripts]
   db_sync_master = "repom.scripts.db_sync_master:main"
   ```

4. **サンプルマスターデータ作成**
   - `data/master/001_sample.py` - Sample モデルのマスターデータ例

### Phase 2: テスト実装

5. **ユニットテスト作成**
   - ファイル読み込みロジックのテスト
   - Upsert ロジックのテスト（新規 INSERT と既存 UPDATE）
   - トランザクションロールバックのテスト
   - 不正なファイル形式のエラーハンドリング

### Phase 3: ドキュメント作成

6. **使用ガイド作成**
   - `docs/guides/master_data_sync_guide.md` - 使い方とベストプラクティス

## テスト計画

### テストケース

1. **正常系**
   - ✅ マスターデータの新規 INSERT
   - ✅ 既存データの UPDATE（id 一致時）
   - ✅ 複数ファイルの順次読み込み
   - ✅ 複数レコードの一括同期

2. **異常系**
   - ✅ 存在しないディレクトリの場合
   - ✅ `MODEL_CLASS` が定義されていない場合
   - ✅ `MASTER_DATA` が定義されていない場合
   - ✅ SQL エラー時のロールバック

3. **パフォーマンス**
   - ✅ 大量データ（1000件）の同期速度

### テスト実行

```bash
poetry run pytest tests/unit_tests/test_db_sync_master.py -v
```

## 実装の詳細

### Upsert ロジック

```python
from repom.session import transaction
from repom.base_repository import BaseRepository

def sync_master_data(model_class, data_list):
    """マスターデータを同期"""
    with transaction() as session:
        repo = BaseRepository(model_class, session)
        for data in data_list:
            # save() は内部で merge() を使用（Upsert）
            instance = model_class(**data)
            repo.save(instance)
```

### ファイル読み込みロジック

```python
import os
import importlib.util

def load_master_data_files(directory):
    """マスターデータファイルを読み込む"""
    files = sorted([f for f in os.listdir(directory) if f.endswith('.py')])
    
    for filename in files:
        filepath = os.path.join(directory, filename)
        spec = importlib.util.spec_from_file_location(filename[:-3], filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, 'MODEL_CLASS'):
            raise ValueError(f"{filename}: MODEL_CLASS が定義されていません")
        if not hasattr(module, 'MASTER_DATA'):
            raise ValueError(f"{filename}: MASTER_DATA が定義されていません")
        
        yield module.MODEL_CLASS, module.MASTER_DATA
```

## 将来的な拡張案（Phase 4 以降）

以下は当面実装せず、必要になったら追加する機能：

- ❌ DELETE 機能（ファイルから削除されたレコードを DB からも削除）
- ❌ バリデーション機能（Pydantic スキーマによる事前検証）
- ❌ ドライラン機能（`--dry-run` オプション）
- ❌ 差分表示機能（変更内容のプレビュー）
- ❌ 環境別マスターデータ（`dev/`, `prod/` ディレクトリ分割）
- ❌ JSON/YAML 形式のサポート

## 関連リソース

### 参考ファイル
- `repom/session.py` - トランザクション管理
- `repom/base_repository.py` - データ保存ロジック
- `repom/scripts/db_create.py` - 既存の CLI スクリプト例

### 関連ドキュメント
- `docs/guides/repository_and_utilities_guide.md` - Repository の使い方
- `docs/guides/session_management_guide.md` - セッション管理

---

## 実装チェックリスト

- [x] `repom/config.py` に `master_data_path` 追加
- [x] `repom/scripts/db_sync_master.py` 作成
- [x] `pyproject.toml` にコマンド登録
- [x] `data_master/001_sample.py` サンプル作成
- [x] `tests/unit_tests/test_db_sync_master.py` テスト作成
- [x] 全テスト通過確認（12/12 テスト成功）
- [x] `docs/guides/master_data_sync_guide.md` ドキュメント作成
- [x] README.md 更新（コマンド追加）

---

## 実装結果

### 実装内容

1. **config.py に master_data_dir プロパティ追加**
   - デフォルト: `root_path / 'data_master'`
   - 自動ディレクトリ作成対応

2. **db_sync_master.py スクリプト実装**
   - ファイル読み込み: `load_master_data_files()`
   - Upsert 処理: `sync_master_data()` - `session.merge()` 使用
   - トランザクション管理: `transaction()` コンテキストマネージャー
   - エラーハンドリング: FileNotFoundError, ValueError

3. **pyproject.toml にコマンド登録**
   - `poetry run db_sync_master`

4. **サンプルマスターデータ作成**
   - `data_master/001_sample.py` - SampleModel 用

5. **テスト実装**
   - 12 テスト全パス
   - 正常系: INSERT, UPDATE, 混在
   - 異常系: ディレクトリなし、MODEL_CLASS なし、不正データ型
   - ロールバック確認

### 動作確認

```bash
$ poetry run db_sync_master

============================================================
マスターデータ同期開始
============================================================

[1/3] モデルをロード中...
✓ モデルのロード完了

[2/3] マスターデータディレクトリ: C:\Users\jj\Desktop\workspace_main\projects\repom\data_master

[3/3] マスターデータを同期中...
  ✓ SampleModel: 3 件

============================================================
同期完了: 1 ファイル、3 レコード
============================================================
```

- ✅ 初回実行: 3 件 INSERT
- ✅ 2回目実行: 3 件 UPDATE（Upsert 動作確認）

---

**最終更新**: 2025-11-19
