# Alembic マイグレーション管理ガイド

repom における Alembic を使ったデータベースマイグレーション管理の方法を説明します。Alembic 自体の詳細は [公式ドキュメント](https://alembic.sqlalchemy.org/) を参照してください。

## 目次

- [セットアップユーティリティ](#セットアップユーティリティ)
  - [AlembicSetup を使った初期化](#alembicsetup-を使った初期化)
  - [CLI コマンドで初期化](#cli-コマンドで初期化)
  - [マイグレーションのリセット](#マイグレーションのリセット)
- [repom 単独での使用](#repom-単独での使用)
- [外部プロジェクトでの使用](#外部プロジェクトでの使用)
- [セキュリティ上の注意](#セキュリティ上の注意)
- [よく使うコマンド](#よく使うコマンド)
- [実践的な例](#実践的な例)
- [トラブルシューティング](#トラブルシューティング)

---

## セットアップユーティリティ

repom 0.x から `AlembicSetup` ユーティリティと CLI コマンドが追加され、Alembic の初期化とリセットが簡単になりました。

### AlembicSetup を使った初期化

プログラムから Alembic 環境を初期化する場合（テストやスクリプトで便利）：

```python
from repom.alembic import AlembicSetup

# 基本的な使い方（repom standalone）
setup = AlembicSetup(
    project_root='<repo-root>',
    db_url='sqlite:///data/db.sqlite3'
)

# alembic.ini と versions/ ディレクトリを作成
setup.create_alembic_ini()
setup.create_version_directory()

# AlembicConfig オブジェクトを取得
alembic_cfg = setup.get_alembic_config()
```

**外部プロジェクトでの使用**:
```python
# mine-py のような外部プロジェクトの場合
setup = AlembicSetup(
    project_root='<consumer-root>',
    db_url='sqlite:///data/mine_py/db.sqlite3',
    script_location='<consumer-root>/submod/repom/alembic',  # repom の alembic ディレクトリ
    version_locations='%(here)s/alembic/versions'  # プロジェクト内の versions
)

setup.create_alembic_ini()
setup.create_version_directory()
```

**オプション**:
- `script_location`: env.py と script.py.mako の場所（デフォルト: `alembic`）
- `version_locations`: マイグレーションファイルの保存場所（デフォルト: `%(here)s/alembic/versions`）
- `version_table`: Alembic のバージョンテーブル名（デフォルト: `alembic_version`）
- `version_table_schema`: Alembic のバージョンテーブルを配置するスキーマ（デフォルト: 明示的なスキーマなし）
- `autogenerate_exclude_tables`: 除外する兄弟名前空間のバージョンテーブル名（文字列またはシーケンス）
- `overwrite`: 既存の alembic.ini を上書きするか（デフォルト: `False`）

### CLI コマンドで初期化

`alembic_init` コマンドで Alembic 環境を簡単に初期化できます。

```bash
# repom プロジェクトで実行
uv run alembic_init

# 出力例:
# ✓ Created alembic.ini: <repo-root>/alembic.ini
# ✓ Created version directory: <repo-root>/alembic/versions
```

**動作**:
- `config.root_path` と `config.db_url` を使用
- alembic.ini を自動生成
- alembic/versions/ ディレクトリを作成
- 上書き保護付き（既存の alembic.ini がある場合はエラー）

### マイグレーションのリセット

開発中にマイグレーション履歴をリセットしたい場合：

```bash
# CLI コマンドで実行（<root_path>/alembic.ini が必要）
uv run alembic_reset

# 別の alembic.ini（別の名前空間）を対象にする場合
uv run alembic_reset -c path/to/alembic.ini

# 動作:
# 1. 選択した alembic.ini の version_table（と version_table_schema）を削除
# 2. その version_locations の *.py を削除（__init__.py は保持）
```

**プログラムから実行**:
```python
setup = AlembicSetup(project_root, db_url)

# マイグレーション履歴とファイルをリセット
setup.reset_migrations(drop_table=True, delete_files=True)

# テーブルのみ削除
setup.reset_migrations(drop_table=True, delete_files=False)

# ファイルのみ削除
setup.reset_migrations(drop_table=False, delete_files=True)
```

**注意**: リセットは**開発環境のみ**で実行してください。本番環境では使用しないでください。

---

## repom 単独での使用

### 環境別のマイグレーション

repom は `EXEC_ENV` 環境変数で環境を切り替えます。

```bash
# 開発環境（デフォルト）
uv run alembic upgrade head
# → data/repom/db.dev.sqlite3 に適用

# テスト環境
EXEC_ENV=test uv run alembic upgrade head
# → data/repom/db.test.sqlite3 に適用

# 本番環境
EXEC_ENV=prod uv run alembic upgrade head
# → data/repom/db.sqlite3 に適用
```

**PowerShell の場合**:
```powershell
$env:EXEC_ENV='dev'; uv run alembic upgrade head
$env:EXEC_ENV='prod'; uv run alembic upgrade head
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

# 独立したマイグレーション名前空間を分離する場合のみ指定
# 省略時は alembic_version
# version_table = alembic_version_fast_domain

# バージョンテーブルを名前付きスキーマに配置する場合のみ指定
# 省略時は明示的なスキーマなし
# version_table_schema = migration_fast_domain

# autogenerate から除外する別名前空間のバージョンテーブル（カンマ区切り）
# autogenerate_exclude_tables = alembic_version_fast_domain
```

**最小限の設定**: 上記のみで動作します。ロギング設定は省略可能です。

複数の独立したマイグレーション名前空間を使用する場合は、それぞれに異なる
`script_location`、`version_locations`、`version_table` を設定します。
スキーマで名前空間を分離する場合は、異なる `version_table_schema` も設定します。
autogenerate は実行中の名前空間のバージョンテーブルだけを除外するため、別の
名前空間のバージョンテーブルを不明なテーブルとして削除する migration を生成する
可能性があります。`autogenerate_exclude_tables` に別名前空間のバージョンテーブルを
カンマ区切りで指定してください。実行中の名前空間の `version_table` は Alembic が
自動的に除外するため、重複して指定する必要はありません。

この設定は別名前空間のバージョンテーブル専用です。実際のモデルテーブルを除外すると
`alembic check` がスキーマ差分を検出できなくなり、安全性が低下します。一般的な
差分抑制には使用せず、生成された migration も必ず確認してください。

### Step 2: ディレクトリを作成

```bash
# mine-py/ で実行
mkdir -p alembic/versions
```

### Step 3: CONFIG_HOOK を設定（オプション）

repom の設定をカスタマイズする場合のみ設定します。

```python
# mine-py/src/mine_py/config.py
def get_repom_config(config):
    config.package_name = 'mine_py'
    config.model_locations = ['mine_py.models']
    config.allowed_package_prefixes = {'mine_py.', 'repom.'}
    return config
```

```bash
# .env ファイル
CONFIG_HOOK=mine_py.config:get_repom_config
```

### Step 4: マイグレーションの実行

```bash
# mine-py/ ディレクトリで実行

# マイグレーションファイルを作成
uv run alembic revision --autogenerate -m "Add custom model"
# → mine-py/alembic/versions/ に作成される

# マイグレーションを実行
uv run alembic upgrade head
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

## セキュリティ上の注意

`alembic.ini` はソースコードと同じ信頼レベルで扱う設定ファイルです。
`pre_migration_hook` は `module:callable` をそのまま解決して呼び出すため、
攻撃者が制御できる値が混入するとコード実行につながります。
`AlembicTemplates.generate_alembic_ini`（`AlembicSetup.create_alembic_ini`
経由の呼び出しも含む）の `script_location`、`version_locations`、
`version_table`、`version_table_schema`、`autogenerate_exclude_tables` には、
リポジトリ名や CI 変数など外部由来の値をそのまま渡さないでください。
改行・復帰・NUL・先頭が `[` の値は例外を送出して拒否されます。
`version_table` / `version_table_schema` / `autogenerate_exclude_tables` の
各要素は `[A-Za-z_][A-Za-z0-9_]*` の識別子パターンのみ許可されます。
`pre_migration_hook` が指すモジュールは `allowed_package_prefixes` で
許可した prefix 配下である必要があり、`alembic/env.py` がインポート前に
これを検証します。

---

## よく使うコマンド

### Alembic 環境の管理

```bash
# Alembic 環境を初期化（alembic.ini + versions/ 作成）
uv run alembic_init

# マイグレーション履歴をリセット（開発時のみ）
uv run alembic_reset
```

### マイグレーション操作

```bash
# マイグレーションファイル作成（自動生成）
uv run alembic revision --autogenerate -m "説明"

# マイグレーション実行
uv run alembic upgrade head

# 現在の状態を確認
uv run alembic current

# 履歴を表示
uv run alembic history

# 1つ戻す
uv run alembic downgrade -1
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
uv run alembic revision --autogenerate -m "Add users table"
uv run alembic upgrade head
```

### 例2: カラムを追加

```python
# モデルに追加
class User(BaseModel):
    # ... 既存のフィールド
    phone: Mapped[str] = mapped_column(String(20), nullable=True)  # 追加
```

```bash
uv run alembic revision --autogenerate -m "Add phone column"
uv run alembic upgrade head
```

### 例3: カラム名を変更

**注意**: 自動検出できないため、手動編集が必要です。

```bash
uv run alembic revision -m "Rename email to email_address"
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

**過去の症状**: 外部プロジェクトの revision が共有 repom checkout の
`alembic/versions/` に作成される

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
$env:EXEC_ENV='prod'; uv run alembic upgrade head

# 間違い（環境変数が残る）
$env:EXEC_ENV='prod'
uv run alembic upgrade head
```

### マイグレーションファイルが見つからない

**エラー**:
```
Can't locate revision identified by 'abc123'
```

**確認方法**:
```bash
# 履歴を確認
uv run alembic history

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
**最終更新**: 2026-02-04  
**更新内容**: AlembicSetup、alembic_init、alembic_reset コマンドの追加
