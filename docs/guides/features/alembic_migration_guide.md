# Alembic マイグレーション管理ガイド

repom における Alembic を使ったデータベースマイグレーション管理の方法を説明します。Alembic 自体の詳細は [公式ドキュメント](https://alembic.sqlalchemy.org/) を参照してください。

## 目次

- [repom 単独での使用](#repom-単独での使用)
- [外部プロジェクトでの使用](#外部プロジェクトでの使用)
- [よく使うコマンド](#よく使うコマンド)
- [実践的な例](#実践的な例)
- [トラブルシューティング](#トラブルシューティング)

---

## repom 単独での使用

### 環境別のマイグレーション

repom は `EXEC_ENV` 環境変数で環境を切り替えます。

```bash
# 開発環境（デフォルト）
poetry run alembic upgrade head
# → data/repom/db.dev.sqlite3 に適用

# テスト環境
EXEC_ENV=test poetry run alembic upgrade head
# → data/repom/db.test.sqlite3 に適用

# 本番環境
EXEC_ENV=prod poetry run alembic upgrade head
# → data/repom/db.sqlite3 に適用
```

**PowerShell の場合**:
```powershell
$env:EXEC_ENV='dev'; poetry run alembic upgrade head
$env:EXEC_ENV='prod'; poetry run alembic upgrade head
```

### ディレクトリ構造

```
repom/
├── alembic/
│   ├── env.py           # 環境設定（EXEC_ENV を使用）
│   └── versions/        # マイグレーションファイル
├── alembic.ini          # Alembic 設定
└── data/
    └── repom/
        ├── db.dev.sqlite3
        ├── db.test.sqlite3
        └── db.sqlite3
```

---

## 外部プロジェクトでの使用

外部プロジェクト（例: mine-py）で repom を使用する場合の設定方法です。

### Step 1: alembic.ini を作成（必須）

**重要**: マイグレーションファイルの保存場所を制御するには `alembic.ini` が**必須**です。

```ini
# mine-py/alembic.ini
[alembic]
# repom の alembic ディレクトリを参照
script_location = submod/repom/alembic

# マイグレーションファイルの保存場所（プロジェクト内）
# %(here)s は alembic.ini のあるディレクトリ
version_locations = %(here)s/alembic/versions
```

**最小限の設定**: 上記のみで動作します。ロギング設定は省略可能です。

### Step 2: ディレクトリを作成

```bash
# mine-py/ で実行
mkdir -p alembic/versions
```

### Step 3: CONFIG_HOOK を設定（オプション）

repom の設定をカスタマイズする場合のみ設定します。

```python
# mine-py/src/mine_py/config.py
from repom.config import RepomConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        # パッケージ名（データディレクトリ: data/mine_py/）
        self.package_name = 'mine_py'
        
        # モデル自動インポート設定
        self.model_locations = ['mine_py.models']
        self.allowed_package_prefixes = {'mine_py.', 'repom.'}

def get_repom_config():
    return MinePyConfig()
```

```bash
# .env ファイル
CONFIG_HOOK=mine_py.config:get_repom_config
```

### Step 4: マイグレーションの実行

```bash
# mine-py/ ディレクトリで実行

# マイグレーションファイルを作成
poetry run alembic revision --autogenerate -m "Add custom model"
# → mine-py/alembic/versions/ に作成される

# マイグレーションを実行
poetry run alembic upgrade head
```

### ディレクトリ構造

```
mine-py/
├── alembic.ini                    # 必須！
├── alembic/
│   └── versions/                  # プロジェクト独自のマイグレーション
│       └── 20260203_xxxx_add_custom_model.py
├── submod/
│   └── repom/                     # repom サブモジュール
│       └── alembic/
│           ├── env.py             # 共有の環境設定
│           └── versions/          # repom のマイグレーション
├── src/
│   └── mine_py/
│       ├── config.py              # CONFIG_HOOK（オプション）
│       └── models/
└── data/
    └── mine_py/                   # CONFIG_HOOK で設定
        └── db.dev.sqlite3
```

---

## よく使うコマンド

```bash
# マイグレーションファイル作成（自動生成）
poetry run alembic revision --autogenerate -m "説明"

# マイグレーション実行
poetry run alembic upgrade head

# 現在の状態を確認
poetry run alembic current

# 履歴を表示
poetry run alembic history

# 1つ戻す
poetry run alembic downgrade -1
```

---

## 実践的な例

### 例1: テーブルを追加

```python
# models/user.py
from repom.models import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

class User(BaseModel):
    __tablename__ = 'users'
    
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
```

```bash
poetry run alembic revision --autogenerate -m "Add users table"
poetry run alembic upgrade head
```

### 例2: カラムを追加

```python
# モデルに追加
class User(BaseModel):
    # ... 既存のフィールド
    phone: Mapped[str] = mapped_column(String(20), nullable=True)  # 追加
```

```bash
poetry run alembic revision --autogenerate -m "Add phone column"
poetry run alembic upgrade head
```

### 例3: カラム名を変更

**注意**: 自動検出できないため、手動編集が必要です。

```bash
poetry run alembic revision -m "Rename email to email_address"
```

```python
# 生成されたファイルを編集
def upgrade() -> None:
    op.alter_column('users', 'email', new_column_name='email_address')

def downgrade() -> None:
    op.alter_column('users', 'email_address', new_column_name='email')
```

### 例4: データ移行

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

def upgrade() -> None:
    # 1. カラムを追加（NULL許可）
    op.add_column('users', sa.Column('status', sa.String(20), nullable=True))
    
    # 2. データを更新
    users_table = table('users', column('status', sa.String))
    op.execute(users_table.update().values(status='active'))
    
    # 3. NOT NULL 制約を追加
    op.alter_column('users', 'status', nullable=False)

def downgrade() -> None:
    op.drop_column('users', 'status')
```

---

## トラブルシューティング

### マイグレーションファイルが repom に作成される

**症状**: 外部プロジェクトで `alembic revision` を実行すると、`repom/alembic/versions/` にファイルが作成される

**解決方法**: プロジェクトのルートに `alembic.ini` を作成し、`version_locations` を設定

```ini
# alembic.ini（必須）
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

詳細: [docs/technical/alembic_version_locations_limitation.md](../../technical/alembic_version_locations_limitation.md)

### モデルの変更が検出されない

**チェックリスト**:
1. モデルが正しくインポートされているか
2. `BaseModel` を継承しているか
3. `__tablename__` を設定しているか

```python
# 正しい例
from repom.models import BaseModel

class User(BaseModel):
    __tablename__ = 'users'  # 必須
```

**デバッグ方法**: `alembic/env.py` で確認
```python
print("Loaded models:", Base.metadata.tables.keys())
```

### 環境変数が反映されない

**PowerShell の正しい書き方**:
```powershell
# 正しい
$env:EXEC_ENV='prod'; poetry run alembic upgrade head

# 間違い（環境変数が残る）
$env:EXEC_ENV='prod'
poetry run alembic upgrade head
```

### マイグレーションファイルが見つからない

**エラー**:
```
Can't locate revision identified by 'abc123'
```

**確認方法**:
```bash
# 履歴を確認
poetry run alembic history

# alembic.ini の version_locations を確認
cat alembic.ini | grep version_locations
```

---

## 関連ドキュメント

- **Alembic 公式**: https://alembic.sqlalchemy.org/
- **技術的な制約**: [alembic_version_locations_limitation.md](../../technical/alembic_version_locations_limitation.md)
- **CONFIG_HOOK ガイド**: [config_hook_guide.md](config_hook_guide.md)

---

**作成日**: 2026-02-03  
**最終更新**: 2026-02-03
