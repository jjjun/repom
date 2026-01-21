# マスターデータ同期ガイド

このガイドでは、`db_sync_master` コマンドを使用したマスターデータの管理方法を説明します。

## 📋 目次

- [概要](#概要)
- [基本的な使い方](#基本的な使い方)
- [マスターデータファイルの作成](#マスターデータファイルの作成)
- [実行方法](#実行方法)
- [ベストプラクティス](#ベストプラクティス)
- [トラブルシューティング](#トラブルシューティング)

---

## 概要

`db_sync_master` は、指定したテーブルにマスターデータを同期（Upsert）するコマンドです。

### 主な機能

- **Upsert**: 既存データは更新、新規データは挿入
- **トランザクション**: 全ファイルを1トランザクションで処理
- **Python ファイル**: コードでマスターデータを定義
- **順序制御**: ファイル名プレフィックスで実行順を制御
- **エラー時ロールバック**: 失敗時は全変更を取り消し

---

## 基本的な使い方

### ディレクトリ構造

```
your_project/
├── data_master/              # マスターデータディレクトリ
│   ├── 001_roles.py         # ロールマスタ
│   ├── 002_users.py         # ユーザーマスタ
│   └── 003_categories.py    # カテゴリマスタ
└── repom/
    └── config.py            # master_data_path 設定
```

### 設定

デフォルトでは `root_path/data_master` がマスターデータディレクトリになります。

```python
# repom/config.py（自動設定）
config.master_data_path  # => "C:/path/to/project/data_master"
```

**カスタマイズ例**:

```python
# mine_py/config.py
from repom.config import MineDbConfig

class MinePyConfig(MineDbConfig):
    def __init__(self):
        super().__init__()
        # カスタムパスを指定
        self.master_data_path = "/custom/path/to/master_data"

def get_repom_config():
    return MinePyConfig()
```

```bash
# .env
CONFIG_HOOK=mine_py.config:get_repom_config
```

---

## マスターデータファイルの作成

### 基本的なファイル形式

```python
# data_master/001_roles.py
from mine_py.models import Role  # モデルクラスをインポート

# どのモデルクラスか指定
MODEL_CLASS = Role

# マスターデータ（辞書のリスト）
MASTER_DATA = [
    {"id": 1, "name": "admin", "description": "Administrator"},
    {"id": 2, "name": "user", "description": "Regular User"},
    {"id": 3, "name": "guest", "description": "Guest User"},
]
```

### 必須要素

1. **`MODEL_CLASS`**: データを挿入するモデルクラス
2. **`MASTER_DATA`**: list 型のデータ（各要素は dict）

### ファイル命名規則

- **プレフィックス**: `001_`, `002_`, `003_` など（実行順序を制御）
- **拡張子**: `.py`（Python ファイル）
- **プライベートファイル**: `_` で始まるファイルは無視される

**例**:

```
data_master/
├── 001_roles.py          # 最初に実行
├── 002_users.py          # 2番目に実行（roles に依存する場合）
├── 003_categories.py     # 3番目に実行
└── _template.py          # 無視される（プライベートファイル）
```

---

## 実行方法

### 基本的な実行

```bash
# デフォルト環境（EXEC_ENV=dev）
poetry run db_sync_master
```

### 環境指定

```bash
# 開発環境
EXEC_ENV=dev poetry run db_sync_master

# 本番環境
EXEC_ENV=prod poetry run db_sync_master

# テスト環境
EXEC_ENV=test poetry run db_sync_master
```

### 実行結果の例

```
============================================================
マスターデータ同期開始
============================================================

[1/3] モデルをロード中...
✓ モデルのロード完了

[2/3] マスターデータディレクトリ: C:\path\to\project\data_master

[3/3] マスターデータを同期中...
  ✓ Role: 3 件
  ✓ User: 5 件
  ✓ Category: 10 件

============================================================
同期完了: 3 ファイル、18 レコード
============================================================
```

---

## ベストプラクティス

### 1. 外部キー制約を考慮した順序

外部キーを持つテーブルは、参照先のテーブルの後に配置します。

```
data_master/
├── 001_roles.py          # 参照される側（先に実行）
├── 002_users.py          # roles を参照（後に実行）
└── 003_user_sessions.py  # users を参照（最後に実行）
```

**例**:

```python
# 001_roles.py（参照される側）
MODEL_CLASS = Role
MASTER_DATA = [
    {"id": 1, "name": "admin"},
]

# 002_users.py（参照する側）
MODEL_CLASS = User
MASTER_DATA = [
    {"id": 1, "name": "Admin User", "role_id": 1},  # roles.id=1 を参照
]
```

### 2. ID を明示的に指定

マスターデータでは `id` を明示的に指定することで、データの一貫性を保ちます。

```python
MASTER_DATA = [
    {"id": 1, "name": "admin"},   # ✅ ID を明示
    {"id": 2, "name": "user"},
]
```

**理由**:
- Upsert 時の一致判定に使用
- データの追跡が容易
- 環境間でのデータ一貫性

### 3. 開発ワークフロー

```bash
# マスターデータを同期
poetry run db_sync_master

# 動作確認
poetry run python -m your_app
```

### 4. バージョン管理

マスターデータファイルは Git で管理します。

```gitignore
# .gitignore
data/              # 一時的なDBファイルは除外
!data_master/      # マスターデータは含める
```

### 5. コメントでドキュメント化

```python
# data_master/001_roles.py
"""
ロールマスターデータ

システムで使用する基本的なロールを定義します。
- admin: システム管理者
- user: 一般ユーザー
- guest: ゲストユーザー

最終更新: 2025-11-19
"""

from mine_py.models import Role

MODEL_CLASS = Role

MASTER_DATA = [
    {
        "id": 1,
        "name": "admin",
        "description": "システム管理者",
        # 注意: admin ロールは削除しないこと
    },
    # ...
]
```

---

## 高度な使い方

### 動的なデータ生成

```python
# data_master/001_categories.py
from mine_py.models import Category
from datetime import datetime

MODEL_CLASS = Category

# 動的にデータを生成
def generate_categories():
    categories = []
    for i in range(1, 11):
        categories.append({
            "id": i,
            "name": f"Category {i}",
            "created_at": datetime.now(),
        })
    return categories

MASTER_DATA = generate_categories()
```

### 条件付きデータ

```python
# data_master/001_config.py
import os
from mine_py.models import Config

MODEL_CLASS = Config

# 環境に応じてデータを変える
EXEC_ENV = os.getenv('EXEC_ENV', 'dev')

if EXEC_ENV == 'prod':
    MASTER_DATA = [
        {"id": 1, "key": "api_url", "value": "https://api.example.com"},
    ]
else:
    MASTER_DATA = [
        {"id": 1, "key": "api_url", "value": "http://localhost:8000"},
    ]
```

### 複雑なリレーション

```python
# data_master/002_users_with_roles.py
from mine_py.models import User

MODEL_CLASS = User

# 複数のロールを持つユーザー（中間テーブル経由）
MASTER_DATA = [
    {
        "id": 1,
        "name": "Admin User",
        "email": "admin@example.com",
        # 注意: 多対多リレーションは別途処理が必要
    },
]
```

---

## トラブルシューティング

### エラー: `MODEL_CLASS が定義されていません`

**原因**: ファイルに `MODEL_CLASS` がありません。

**解決策**:

```python
# 正しい形式
from mine_py.models import Role

MODEL_CLASS = Role  # 必須

MASTER_DATA = [...]
```

### エラー: `MASTER_DATA は list 型である必要があります`

**原因**: `MASTER_DATA` が list 型ではありません。

**解決策**:

```python
# ❌ 間違い
MASTER_DATA = {"id": 1, "name": "test"}

# ✅ 正しい
MASTER_DATA = [
    {"id": 1, "name": "test"},
]
```

### エラー: `no such table: xxx`

**原因**: テーブルが存在しません。

**解決策**: テーブルを作成してから実行してください。

### エラー: 外部キー制約違反

**原因**: 参照先のレコードが存在しない、またはファイルの順序が間違っている。

**解決策**:

1. ファイルの順序を確認（参照される側を先に実行）
2. 参照先のIDが正しいか確認

```python
# 001_roles.py（先に実行）
MASTER_DATA = [
    {"id": 1, "name": "admin"},  # このIDが存在する必要がある
]

# 002_users.py（後に実行）
MASTER_DATA = [
    {"id": 1, "name": "Admin", "role_id": 1},  # role_id=1 を参照
]
```

### データが更新されない

**原因**: Upsert は `id` で判定しています。`id` が一致しない場合は新規 INSERT されます。

**確認方法**:

```python
# マスターデータ
MASTER_DATA = [
    {"id": 1, "name": "updated name"},  # id=1 が存在すれば UPDATE
]
```

**ログを確認**:

```bash
poetry run db_sync_master
# 出力: ✓ ModelName: 3 件
```

---

## まとめ

### コマンド早見表

```bash
# 基本実行
poetry run db_sync_master

# 環境指定
EXEC_ENV=dev poetry run db_sync_master
EXEC_ENV=prod poetry run db_sync_master
```

### チェックリスト

開発時のチェックリスト：

- [ ] マスターデータファイルに `MODEL_CLASS` と `MASTER_DATA` を定義
- [ ] ファイル名にプレフィックス（`001_`, `002_`）を付与
- [ ] 外部キー制約を考慮した順序でファイルを配置
- [ ] `id` を明示的に指定
- [ ] Git でバージョン管理
- [ ] 実行前にバックアップ作成（`poetry run db_backup`）

---

## 関連ドキュメント

- **[セッション管理ガイド](session_management_guide.md)** - `transaction()` の詳細
- **[BaseRepository ガイド](repository_and_utilities_guide.md)** - データ操作の詳細
- **[README.md](../../README.md)** - コマンドリファレンス

---

**最終更新**: 2025-11-19
