# Issue #026: PostgreSQL Docker セットアップスクリプト

## ステータス
- **作成日**: 2026-02-01
- **優先度**: 高
- **複雑度**: 中
- **ステータス**: 📝 計画中

## 概要

repom プロジェクトに PostgreSQL を Docker で簡単にセットアップできる管理スクリプトを追加する。
`repom/scripts/postgresql/` ディレクトリ配下に Docker 関連のスクリプトと設定ファイルを配置し、開発者が簡単に PostgreSQL 環境を構築できるようにする。

## 問題説明

現在、repom は SQLite のみをサポートしているが、本番環境では PostgreSQL を使用するケースが多い。
開発環境で PostgreSQL を使うには手動で Docker をセットアップする必要があり、開発者によって環境が異なる可能性がある。

## 期待される動作

- `poetry run docker_start` で PostgreSQL が起動
- `poetry run docker_stop` で PostgreSQL が停止
- 環境別のデータベース（dev/test/prod）が自動作成される
- 接続確認（health check）が自動実行される
- Docker Compose で管理され、設定が一元化される

## 実装計画

### 1. ディレクトリ構造

```
repom/scripts/postgresql/
├── docker-compose.yml      # Docker Compose 設定
├── init/                   # 初期化スクリプト
│   └── 01_init_databases.sql  # 環境別DB作成
└── manage.py               # 管理スクリプト
```

### 2. docker-compose.yml の作成

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

### 3. 初期化スクリプト (init/01_init_databases.sql)

```sql
-- 環境別のデータベースを作成
CREATE DATABASE repom_test;
GRANT ALL PRIVILEGES ON DATABASE repom_test TO repom;

CREATE DATABASE repom_prod;
GRANT ALL PRIVILEGES ON DATABASE repom_prod TO repom;
```

### 4. 管理スクリプト (manage.py)

```python
"""PostgreSQL Docker 環境管理スクリプト"""
import subprocess
import time
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
COMPOSE_FILE = SCRIPT_DIR / "docker-compose.yml"

def start():
    """PostgreSQL を起動"""
    print("🐳 Starting PostgreSQL container...")
    subprocess.run(
        ["docker-compose", "-f", str(COMPOSE_FILE), "up", "-d"],
        check=True
    )
    print("⏳ Waiting for PostgreSQL to be ready...")
    wait_for_postgres()
    print("✅ PostgreSQL is ready")

def stop():
    """PostgreSQL を停止"""
    print("🛑 Stopping PostgreSQL container...")
    subprocess.run(
        ["docker-compose", "-f", str(COMPOSE_FILE), "down"],
        check=True
    )
    print("✅ PostgreSQL stopped")

def wait_for_postgres(max_retries=30):
    """PostgreSQL の起動を待機"""
    for i in range(max_retries):
        result = subprocess.run(
            ["docker", "exec", "repom_postgres", "pg_isready", "-U", "repom"],
            capture_output=True
        )
        if result.returncode == 0:
            return True
        time.sleep(1)
    raise TimeoutError("PostgreSQL did not start in time")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage.py [start|stop]")
        sys.exit(1)
    
    command = sys.argv[1]
    if command == "start":
        start()
    elif command == "stop":
        stop()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
```

### 5. Poetry スクリプトの追加

```toml
# pyproject.toml
[tool.poetry.scripts]
postgres_start = "repom.scripts.postgresql.manage:start"
postgres_stop = "repom.scripts.postgresql.manage:stop"
```

## テスト計画

### 手動テスト

```bash
# 起動テスト
poetry run postgres_start

# 接続確認
docker exec repom_postgres psql -U repom -d repom_dev -c "SELECT 1;"

# 環境別DB確認
docker exec repom_postgres psql -U repom -c "\l"

# 停止テスト
poetry run postgres_stop
```

### 自動テスト

```python
# tests/integration_tests/test_postgresql_docker.py
def test_postgres_start_stop():
    """PostgreSQL の起動・停止をテスト"""
    # 起動
    result = subprocess.run(["poetry", "run", "postgres_start"])
    assert result.returncode == 0
    
    # 接続確認
    result = subprocess.run([
        "docker", "exec", "repom_postgres",
        "pg_isready", "-U", "repom"
    ])
    assert result.returncode == 0
    
    # 停止
    result = subprocess.run(["poetry", "run", "postgres_stop"])
    assert result.returncode == 0
```

## 完了基準

- [ ] `repom/scripts/postgresql/` ディレクトリ構造が作成されている
- [ ] `docker-compose.yml` が正しく動作する
- [ ] `manage.py` で起動・停止ができる
- [ ] 環境別データベース（dev/test/prod）が自動作成される
- [ ] Poetry スクリプトが登録されている（`postgres_start`, `postgres_stop`）
- [ ] health check が正しく動作する
- [ ] 手動テストがすべてパスする
- [ ] ドキュメントが更新されている（README.md に使い方を追加）

## 関連ドキュメント

- **Issue #027**: PostgreSQL 設定切り替え対応（config での切り替え）
- **docs/guides/**: PostgreSQL セットアップガイド（作成予定）

## 依存関係

- **Issue #027 との関係**: このスクリプトが完成した後、#027 で config での切り替えを実装

## 注意事項

- Docker Desktop がインストールされている必要がある
- Windows/Mac/Linux で動作することを確認
- ポート 5432 が使用可能である必要がある
- データは Docker Volume で永続化される（`postgres_data`）

---

**作成日**: 2026-02-01  
**最終更新**: 2026-02-01
