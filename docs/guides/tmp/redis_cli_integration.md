# Redis CLI 統合ガイド（fast-domain 向け）

**対象**: fast-domain で `poetry run redis_*` コマンドを統合する開発者  

---

## 📋 実装チェックリスト

- [ ] `poetry run redis_generate` コマンド
- [ ] `poetry run redis_start` コマンド
- [ ] `poetry run redis_stop` コマンド
- [ ] `poetry run redis_remove` コマンド
- [ ] オプション: `poetry run redis_status` コマンド

---

## pyproject.toml 設定

```toml
# fast-domain/pyproject.toml

[tool.poetry.scripts]
redis_generate = "fast_domain.docker.redis_manager:generate"
redis_start = "fast_domain.docker.redis_manager:start"
redis_stop = "fast_domain.docker.redis_manager:stop"
redis_remove = "fast_domain.docker.redis_manager:remove"
redis_status = "fast_domain.docker.redis_manager:status"  # オプション
```

---

## 実装コード例

### redis_manager.py の main 関数群

```python
# fast-domain/src/fast_domain/docker/redis_manager.py

import sys
from pathlib import Path


def get_compose_dir() -> Path:
    """docker-compose.yml の配置ディレクトリを取得"""
    compose_dir = Path.cwd() / "infrastructure"
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir


def generate():
    """docker-compose.yml を生成
    
    使用方法:
        poetry run redis_generate
    """
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    
    # YAML 生成ロジック
    import yaml
    config = {
        "version": "3.8",
        "services": {
            "redis": {
                "image": "redis:7-alpine",
                "container_name": "fast_domain_redis",
                "ports": ["6379:6379"],
                "volumes": ["fast_domain_redis_data:/data"],
                "command": "redis-server --appendonly yes",
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "5s",
                    "timeout": "3s",
                    "retries": 5
                }
            }
        },
        "volumes": {
            "fast_domain_redis_data": {}
        }
    }
    
    compose_file.write_text(yaml.dump(config), encoding="utf-8")
    
    print(f"✅ Generated: {compose_file}")
    print()
    print("📦 Redis Service:")
    print(f"  Container: fast_domain_redis")
    print(f"  Port: 6379")
    print(f"  Volume: fast_domain_redis_data")


def start():
    """Redis を起動
    
    使用方法:
        poetry run redis_start
    
    処理:
        1. docker-compose.yml を生成
        2. redis コンテナを起動
        3. redis-cli ping で起動確認
    """
    generate()
    
    print()
    manager = RedisManager(get_compose_dir())
    
    try:
        manager.start()
        manager.print_connection_info()
    except TimeoutError as e:
        print(f"❌ {e}")
        print(f"Check logs: docker logs {manager.get_container_name()}")
        sys.exit(1)


def stop():
    """Redis を停止
    
    使用方法:
        poetry run redis_stop
    
    処理:
        1. docker-compose.yml を確認
        2. redis コンテナを停止（削除しない）
    """
    manager = RedisManager(get_compose_dir())
    
    try:
        manager.stop()
    except SystemExit:
        raise


def remove():
    """Redis を削除（完全リセット）
    
    使用方法:
        poetry run redis_remove
    
    処理:
        1. docker-compose.yml を確認
        2. redis コンテナを削除
        3. ボリュームも削除
    """
    manager = RedisManager(get_compose_dir())
    
    try:
        manager.remove()
    except SystemExit:
        raise


def status():
    """Redis のステータス確認（オプション）
    
    使用方法:
        poetry run redis_status
    """
    manager = RedisManager(get_compose_dir())
    
    is_running = manager.is_running()
    print(f"Redis: {'🟢 Running' if is_running else '🔴 Stopped'}")
    
    if is_running:
        manager.print_connection_info()
```

---

## 使用例

### 1. Redis を起動

```bash
$ poetry run redis_generate
✅ Generated: /path/to/infrastructure/docker-compose.generated.yml

📦 Redis Service:
  Container: fast_domain_redis
  Port: 6379
  Volume: fast_domain_redis_data

$ poetry run redis_start
🐳 Starting fast_domain_redis container...
⏳ Waiting for service to be ready...
✅ Redis is ready

📦 Redis Connection:
  Host: localhost
  Port: 6379
  Database: 0 (default)
```

### 2. Redis に接続

```bash
# redis-cli で接続
$ redis-cli
127.0.0.1:6379> PING
PONG

127.0.0.1:6379> SET key value
OK

127.0.0.1:6379> GET key
"value"
```

### 3. ステータス確認（オプション）

```bash
$ poetry run redis_status
Redis: 🟢 Running

📦 Redis Connection:
  Host: localhost
  Port: 6379
  Database: 0 (default)
```

### 4. Redis を停止

```bash
$ poetry run redis_stop
🛑 Stopping fast_domain_redis container...
✅ fast_domain_redis stopped
```

### 5. Redis を完全削除

```bash
$ poetry run redis_remove
🧹 Removing fast_domain_redis container and volumes...
✅ fast_domain_redis removed
```

---

## スクリプト作成例（bash）

`Makefile` で簡単にしたい場合：

```makefile
.PHONY: redis-generate redis-start redis-stop redis-remove redis-status

redis-generate:
	poetry run redis_generate

redis-start: redis-generate
	poetry run redis_start

redis-stop:
	poetry run redis_stop

redis-remove:
	poetry run redis_remove

redis-status:
	poetry run redis_status

redis-restart: redis-stop redis-start
	@echo "Redis restarted"
```

使用：

```bash
make redis-start
make redis-status
make redis-restart
make redis-remove
```

---

## 環境変数での制御（ホスト/ポート カスタマイズ）

```python
# fast-domain/src/fast_domain/docker/redis_manager.py に追加

import os


def get_redis_port() -> int:
    """Redis ポートを取得（環境変数で制御可能）"""
    return int(os.getenv("REDIS_PORT", "6379"))


def get_redis_host() -> str:
    """Redis ホストを取得"""
    return os.getenv("REDIS_HOST", "localhost")


def generate():
    """docker-compose.yml を生成（環境変数対応）"""
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    
    import yaml
    config = {
        "version": "3.8",
        "services": {
            "redis": {
                "image": "redis:7-alpine",
                "container_name": "fast_domain_redis",
                "ports": [f"{get_redis_port()}:6379"],  # ← このポートは可変
                "volumes": ["fast_domain_redis_data:/data"],
                "command": "redis-server --appendonly yes"
            }
        },
        "volumes": {
            "fast_domain_redis_data": {}
        }
    }
    
    compose_file.write_text(yaml.dump(config), encoding="utf-8")
    print(f"✅ Generated: {compose_file}")
```

使用例：

```bash
# デフォルトポート（6379）で起動
poetry run redis_start

# カスタムポート（6380）で起動
REDIS_PORT=6380 poetry run redis_start
```

---

## Docker 環境変数での起動（オプション）

`.env` ファイル：

```bash
# .env
REDIS_PORT=6379
REDIS_HOST=localhost
REDIS_IMAGE=redis:7-alpine
REDIS_MEMORY_LIMIT=512m
```

Python で読み込み：

```python
from dotenv import load_dotenv

load_dotenv()

def get_redis_config():
    return {
        "port": os.getenv("REDIS_PORT", "6379"),
        "host": os.getenv("REDIS_HOST", "localhost"),
        "image": os.getenv("REDIS_IMAGE", "redis:7-alpine"),
    }
```

---

## トラブルシューティング

### コマンドが見つからない

```bash
# pyproject.toml を確認
cat pyproject.toml | grep redis_

# Poetry 環境を再構築
poetry lock
poetry install
```

### ポート競合

```bash
# 既に 6379 で何かが動作している
$ poetry run redis_start
❌ Failed to start Redis...

# ポート確認
netstat -tulpn | grep 6379

# カスタムポートで起動
REDIS_PORT=6380 poetry run redis_start
```

### Docker が見つからない

```bash
# Docker がインストールされていることを確認
docker --version

# Docker Desktop が起動していることを確認
docker ps
```

---

## テスト（CLI が正しく動作するか）

```python
# tests/test_redis_cli.py

def test_redis_generate_creates_compose_file(tmp_path):
    """generate コマンドが docker-compose.yml を作成"""
    # テスト実装
    pass

def test_redis_start_uses_manager(monkeypatch):
    """start コマンドが RedisManager を使用"""
    from fast_domain.docker.redis_manager import start
    
    # start() が呼ばれることを確認
    assert callable(start)
```

---

## Development ワークフロー

```bash
# 1. Redis を起動
poetry run redis_start

# 2. アプリケーション開発
# ... code ...

# 3. テスト実行
poetry run pytest

# 4. Redis を停止（結果保持）
poetry run redis_stop

# 5. 完全リセット（環境をクリア）
poetry run redis_remove
```

---

## CI/CD 統合例

### GitHub Actions

```yaml
# .github/workflows/test-with-redis.yml

name: Tests with Redis

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: poetry install
      
      - name: Start Redis
        run: poetry run redis_start
      
      - name: Run tests
        run: poetry run pytest
      
      - name: Stop Redis
        run: poetry run redis_stop
        if: always()
```

---

## 参考資料

- [PostgreSQL CLI 統合例](../../repom/postgres/manage.py)
- [Poetry スクリプト作成](https://python-poetry.org/docs/pyproject/#scripts)
- [Docker Compose CLI](https://docs.docker.com/compose/reference/)

---

**実装予想時間**: 30分-1時間
