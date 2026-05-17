# PostgreSQL セットアップガイド

このガイドでは、repom で PostgreSQL を使用するための環境構築方法を説明します。

## 📋 目次

- [概要](#概要)
- [前提条件](#前提条件)
- [セットアップ手順](#セットアップ手順)
- [使い方](#使い方)
- [接続情報](#接続情報)
- [データベース構成](#データベース構成)
- [トラブルシューティング](#トラブルシューティング)

---

## 概要

repom は Docker Compose を使用して PostgreSQL 環境を自動的にセットアップします。

### 主な機能

- ✅ **ワンコマンド起動**: `uv run postgres_start` で完全自動セットアップ
- ✅ **環境別データベース**: dev/test/prod 用のデータベースを自動作成
- ✅ **データ永続化**: Docker Volume でデータを保存
- ✅ **Health Check**: 起動完了を自動確認
- ✅ **クリーンな停止**: `uv run postgres_stop` で完全クリーンアップ

---

## 前提条件

### 必須

- **Docker Desktop**: Windows/Mac/Linux 用
  - インストール: https://www.docker.com/products/docker-desktop
  - バージョン: 20.10 以上推奨

### 確認コマンド

```powershell
# Docker が動作しているか確認
docker --version
# 出力例: Docker version 24.0.7, build afdd53b

# Docker Compose が使えるか確認
docker-compose --version
# 出力例: Docker Compose version v2.23.3
```

---

## セットアップ手順

### 1. PostgreSQL を起動

```powershell
uv run postgres_start
```

**初回実行時の動作**:
```
🐳 Starting PostgreSQL container...
Pulling postgres (postgres:16-alpine)...
16-alpine: Pulling from library/postgres
...
Creating repom_postgres ... done
⏳ Waiting for PostgreSQL to be ready...
✅ PostgreSQL is ready

Connection info:
  Host: localhost
  Port: 5432
  User: repom
  Password: repom_dev
  Databases: repom_dev, repom_test, repom_prod
```

**所要時間**:
- 初回: 約30秒～1分（イメージダウンロード含む）
- 2回目以降: 約5秒

### 2. 接続確認

```powershell
# PostgreSQL のバージョン確認
docker exec repom_postgres psql -U repom -d repom_dev -c "SELECT version();"

# データベース一覧を確認
docker exec repom_postgres psql -U repom -d repom_dev -c "\l"
```

**期待される出力**:
```
PostgreSQL 16.11 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit

    Name    | Owner | ...
------------+-------+-----
 repom_dev  | repom | ...
 repom_test | repom | ...
 repom_prod | repom | ...
```

### 3. 使用が終わったら停止

```powershell
uv run postgres_stop
```

**動作**:
```
🛑 Stopping PostgreSQL container...
Stopping repom_postgres ... done
Removing repom_postgres ... done
Removing network postgresql_default
✅ PostgreSQL stopped
```

**注意**: コンテナは削除されますが、データは Docker Volume に保存されているため、次回起動時にも残っています。

---

## 使い方

### 基本操作

```powershell
# 起動
uv run postgres_start

# 停止
uv run postgres_stop

# ステータス確認
docker ps | Select-String repom_postgres

# ログ確認
docker logs repom_postgres

# PostgreSQL に直接接続（psql）
docker exec -it repom_postgres psql -U repom -d repom_dev
```

### データベースの切り替え

```sql
-- repom_dev（開発環境）に接続
\c repom_dev

-- repom_test（テスト環境）に接続
\c repom_test

-- repom_prod（本番環境）に接続
\c repom_prod
```

### データベースのリセット

```powershell
# 完全にリセット（データも削除）
uv run postgres_stop
docker volume rm postgresql_postgres_data
uv run postgres_start
```

---

## 接続情報

### デフォルト設定

| 項目 | 値 |
|------|-----|
| **Host** | `localhost` |
| **Port** | `5432` |
| **User** | `repom` |
| **Password** | `repom_dev` |

### 接続文字列

```python
# SQLAlchemy URL（開発環境）
DATABASE_URL = "postgresql+psycopg://repom:repom_dev@localhost:5432/repom_dev"

# 環境別
dev_url  = "postgresql+psycopg://repom:repom_dev@localhost:5432/repom_dev"
test_url = "postgresql+psycopg://repom:repom_dev@localhost:5432/repom_test"
prod_url = "postgresql+psycopg://repom:repom_dev@localhost:5432/repom_prod"
```

### DBeaver での接続

1. **新しい接続を作成**
2. **PostgreSQL** を選択
3. **設定を入力**:
   - Host: `localhost`
   - Port: `5432`
   - Database: `repom_dev`（または `repom_test`, `repom_prod`）
   - Username: `repom`
   - Password: `repom_dev`
4. **接続をテスト**
5. **完了**

---

## データベース構成

### 自動作成されるデータベース

| データベース名 | 用途 | 作成タイミング |
|--------------|------|---------------|
| `repom_dev` | 開発環境 | 初回起動時（docker-compose.yml） |
| `repom_test` | テスト環境 | 初回起動時（init スクリプト） |
| `repom_prod` | 本番環境 | 初回起動時（init スクリプト） |

### ディレクトリ構成

```
repom/postgres/
├── docker-compose.template.yml  # Docker Compose 参考テンプレート
├── init.template/               # 初期化スクリプトテンプレート
│   └── 01_init_databases.sql     # 環境別DB作成
└── manage.py                     # 管理スクリプト
```

### docker-compose.yml の内容

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: repom_postgres
    environment:
      POSTGRES_USER: repom
      POSTGRES_PASSWORD: repom_dev
      POSTGRES_DB: repom_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U repom"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 初期化スクリプト

初回起動時に `init/01_init_databases.sql` が自動実行され、環境別データベースが作成されます：

```sql
-- テスト環境用
CREATE DATABASE repom_test;
GRANT ALL PRIVILEGES ON DATABASE repom_test TO repom;

-- 本番環境用
CREATE DATABASE repom_prod;
GRANT ALL PRIVILEGES ON DATABASE repom_prod TO repom;
```

---

## トラブルシューティング

### ポート 5432 が既に使用されている

**エラー**:
```
Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind: address already in use
```

**原因**: 既に PostgreSQL が動作している

**解決方法**:

```powershell
# 既存の PostgreSQL プロセスを確認
Get-Process postgres

# 他の PostgreSQL を停止するか、ポートを変更
# docker-compose.yml で以下を変更:
ports:
  - "5433:5432"  # ホスト側を 5433 に変更
```

### Docker Desktop が起動していない

**エラー**:
```
Cannot connect to the Docker daemon
```

**解決方法**:
1. Docker Desktop を起動
2. システムトレイで Docker アイコンが表示されるまで待つ
3. 再度 `uv run postgres_start` を実行

### コンテナが起動しない

**確認コマンド**:
```powershell
# ログを確認
docker logs repom_postgres

# コンテナの状態を確認
docker ps -a | Select-String repom_postgres
```

**よくある原因**:
- メモリ不足: Docker Desktop の設定でメモリを増やす
- ディスク容量不足: 不要なイメージを削除（`docker system prune`）

### データベースが見つからない

**エラー**:
```
FATAL: database "repom" does not exist
```

**解決方法**:

```powershell
# データベース名を正しく指定
docker exec repom_postgres psql -U repom -d repom_dev -c "\l"

# または、接続時にデータベースを指定
psql -h localhost -U repom -d repom_dev
```

### データが消えた

**原因**: Docker Volume が削除された

**データの永続性を確認**:
```powershell
# Volume が存在するか確認
docker volume ls | Select-String postgres_data

# Volume の詳細を確認
docker volume inspect postgresql_postgres_data
```

**バックアップ方法**:
```powershell
# データベースをバックアップ
docker exec repom_postgres pg_dump -U repom repom_dev > backup.sql

# リストア
docker exec -i repom_postgres psql -U repom -d repom_dev < backup.sql
```

### ポートが既に使われている

```
Error: Bind for 0.0.0.0:5432 failed: port is already allocated
```

**原因**: 別の PostgreSQL プロセスまたは他のプロジェクトのコンテナが 5432 ポートを使用している

**解決策 1**: CONFIG_HOOK でポートを変更

```python
# config.py
def hook_config(config: RepomConfig) -> RepomConfig:
    config.postgres.container.host_port = 5433  # 別のポートを使用
    return config
```

**解決策 2**: 競合しているプロジェクトを停止

```powershell
# 他のプロジェクトの PostgreSQL を停止
cd other-project
uv run postgres_stop
```

### コンテナ名が既に使われている

```
Error: Container name "repom_postgres" is already in use
```

**原因**: 別のプロジェクトが同じコンテナ名を使用している

**解決策**: CONFIG_HOOK でコンテナ名をカスタマイズ

```python
# config.py
def hook_config(config: RepomConfig) -> RepomConfig:
    config.postgres.container.container_name = "my_postgres"  # カスタムコンテナ名
    return config
```

### コンテナを完全にリセットしたい

```powershell
# 1. コンテナを停止・削除
uv run postgres_stop

# 2. Volume を削除（データも削除される）
docker volume rm repom_postgres_data

# 3. イメージも削除（完全クリーン）
docker rmi postgres:16-alpine

# 4. 再起動（すべてダウンロードし直す）
uv run postgres_start
```

---

## 高度な使い方

### 複数プロジェクトでの並行開発（CONFIG_HOOK）

repom をベースとする複数のプロジェクト（mine-py, fast-domain など）を同時に開発する場合、CONFIG_HOOK を使ってプロジェクトごとに独立した PostgreSQL 環境を構築できます。

#### 設定例: mine-py プロジェクト

```python
# mine_py/config.py
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
    # **重要**: コンテナ名を設定（Docker Compose プロジェクト名に使われる）
    config.postgres.container.container_name = "mine_py_postgres"
    
    # ポートをずらす（repom: 5432, mine_py: 5433）
    config.postgres.port = 5433
    config.postgres.container.host_port = 5433
    
    # DB 設定をプロジェクト名に合わせる
    config.postgres.user = "mine_py"
    config.postgres.password = "mine_py_dev"
    
    return config
```

```bash
# mine_py/.env
CONFIG_HOOK=mine_py.config:hook_config
```

**重要**: `container_name` を設定することで、Docker Compose のプロジェクト名が分離され、コンテナ名の衝突が防げます。

#### 起動

```powershell
# repom プロジェクト（container_name = "repom_postgres"）
cd repom
uv run postgres_start
# → Container: repom_postgres, Port: 5432

# mine-py プロジェクト（container_name = "mine_py_postgres"）同時起動可能
cd mine-py
uv run postgres_start
# → Container: mine_py_postgres, Port: 5433
```

#### 生成されるファイル

```
data/
├── repom/                                 # repom プロジェクト用
│   ├── docker-compose.generated.yml
│   └── postgresql_init/
│       └── 01_init_databases.sql
│
└── mine_py/                              # mine-py プロジェクト用
    ├── docker-compose.generated.yml
    └── postgresql_init/
        └── 01_init_databases.sql
```

### docker-compose.yml の事前確認

```powershell
# 設定ファイルを生成（起動せずに確認）
uv run postgres_generate

# 生成されたファイルを確認
cat data/repom/docker-compose.generated.yml
cat data/repom/postgresql_init/01_init_databases.sql
```

### カスタマイズ

CONFIG_HOOK を使ってカスタマイズする方法（推奨）：

```python
# your_project/config.py
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
    # ポート変更
    config.postgres.container.host_port = 5433
    
    # イメージ変更
    config.postgres.container.image = "postgres:15-alpine"
    
    # コンテナ名を明示的に指定
    config.postgres.container.container_name = "my_custom_postgres"
    
    # Volume 名を明示的に指定
    config.postgres.container.volume_name = "my_custom_data"
    
    return config
```

### 複数バージョンの PostgreSQL

```yaml38](../../issue/active/038_postgresql_container_customization.md)**: PostgreSQL コンテナ設定のカスタマイズ対応
- **[Docker Compose 基盤ガイド](../features/docker_compose_guide.md)**: 汎用 Docker Compose 基盤の使い方
- **[CONFIG_HOOK ガイド](../features/config_hook_guide.md)**: 設定のカスタマイズ方法
- **[README.md](../../../README.md)**: repom 全体のドキュメント

---

**作成日**: 2026-02-01  
**最終更新**: 2026-02-22

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: repom
          POSTGRES_PASSWORD: repom_dev
          POSTGRES_DB: repom_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
```

---

## 次のステップ

- **Issue #027**: PostgreSQL 設定切り替え対応
  - `DB_TYPE=postgres` で SQLite と切り替え可能に
  - repom の config から PostgreSQL を使用

---

## 関連ドキュメント

- **[Issue #026](../../issue/active/026_postgresql_docker_setup.md)**: PostgreSQL Docker セットアップ仕様
- **[Issue #027](../../issue/active/027_postgresql_config_integration.md)**: PostgreSQL 設定切り替え（次のステップ）
- **[README.md](../../../README.md)**: repom 全体のドキュメント

---

**作成日**: 2026-02-01  
**最終更新**: 2026-02-01  
**対象バージョン**: repom v0.1.0+
