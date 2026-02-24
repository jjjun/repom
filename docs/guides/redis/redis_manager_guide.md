# Redis Manager ガイド

**対象**: repom を使用するプロジェクトで Redis を管理する開発者  
**作成日**: 2026-02-23

---

##  目次

1. [概要](#概要)
2. [クイックスタート](#クイックスタート)
3. [基本的な使い方](#基本的な使い方)
4. [API リファレンス](#apiリファレンス)
5. [環境設定](#環境設定)
6. [RedisConfig 設定ガイド](#redisconfig設定ガイド)
7. [トラブルシューティング](#トラブルシューティング)
8. [Redis CLI コマンド](#redisコマンドリファレンス)

---

## 概要

Redis Manager は **repom に統合された Redis コンテナ管理ツール** です。PostgreSQL と同じインターフェースで Redis 環境を統一的に管理できます。

### 特徴

- ✅ **簡単セットアップ**: `poetry run redis_generate` で構成自動生成
- ✅ **統一インターフェース**: PostgreSQL と同じパターン
- ✅ **健全性確認**: `redis-cli ping` で確実な起動確認
- ✅ **持続化対応**: AOF（Append Only File）による永続化設定
- ✅ **設定可能**: 環境変数でカスタマイズ可能

### アーキテクチャ

```
repom/redis/
├── manage.py                  # RedisManager クラス
├── docker-compose.template.yml  # Docker Compose テンプレート
├── init.template/redis.conf   # Redis 設定テンプレート
└── __init__.py

CLI コマンド (poetry run)
├── redis_generate   # docker-compose + redis.conf 生成
├── redis_start      # Redis 起動
├── redis_stop       # Redis 停止
└── redis_remove     # Redis 削除
```

---

## クイックスタート

### 1. Redis を生成

```bash
poetry run redis_generate
```

**出力例**:
```
✅ Generated: C:\...\data\repom\docker-compose.generated.yml
   Config: C:\...\data\repom\redis_init\redis.conf

📦 Redis Service:
   Container: repom_redis
   Port: 6379
   Volume: repom_redis_data
```

### 2. Redis を起動

```bash
poetry run redis_start
```

**出力例**:
```
🐳 Starting repom_redis...
✅ Redis started

📦 Redis Connection:
  Host: localhost
  Port: 6379
  CLI: redis-cli -p 6379

```

### 3. Redis に接続

```bash
# Docker 経由で実行
docker exec -it repom_redis redis-cli

# または、ホストに redis-cli がインストールされている場合
redis-cli -p 6379
```

### 4. Redis を停止

```bash
poetry run redis_stop
```

---

## 基本的な使い方

### Python から Redis を使用

```python
import redis

# Redis に接続
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# キーを設定
r.set('mykey', 'myvalue')

# キーを取得
value = r.get('mykey')
print(value)  # 'myvalue'

# キーの有効期限を設定（10秒）
r.setex('temporary', 10, 'value')

# キーの一覧
keys = r.keys('*')

# クリア
r.flushdb()
```

### FastAPI から Redis を使用

```python
from fastapi import FastAPI
import redis

app = FastAPI()

# Redis クライアントを作成
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

@app.get('/cache/{key}')
async def get_cache(key: str):
    value = redis_client.get(key)
    return {'key': key, 'value': value}

@app.post('/cache/{key}')
async def set_cache(key: str, value: str):
    redis_client.set(key, value)
    return {'key': key, 'value': value}
```

---

## API リファレンス

### RedisManager クラス

#### メソッド

**`get_container_name() -> str`**
- Redis コンテナ名を取得
- **config を経由**: `config.redis.container.get_container_name()` を使用
- 戻り値: デフォルト `"repom_redis"` (カスタマイズ可能)

```python
from repom.redis.manage import RedisManager
from repom.config import config

manager = RedisManager()
container_name = manager.get_container_name()
print(container_name)  # repom_redis (config 値)

# config 経由の取得
print(config.redis.container.get_container_name())
print(config.redis.container.get_volume_name())
```

**`get_compose_file_path() -> Path`**
- docker-compose.yml のパスを取得
- 戻り値: `data/repom/docker-compose.generated.yml`

```python
path = manager.get_compose_file_path()
print(path)  # /workspace/data/repom/docker-compose.generated.yml
```

**`start()`**
- Redis を起動
- 内部で `generate()` を実行して環境を生成

```python
manager.start()  # Redis が起動する
```

**`stop()`**
- Redis を停止（コンテナ停止のみ、削除なし）

```python
manager.stop()  # Redis が停止する
```

**`remove()`**
- Redis を削除（コンテナと Volume を完全削除）

```python
manager.remove()  # Redis が削除される
```

**`status() -> bool`**
- Redis が実行中かを確認

```python
is_running = manager.status()
print(is_running)  # True or False
```

**`wait_for_service(max_retries: int = 30)`**
- Redis の起動を待機
- `redis-cli ping` で確実な起動確認

```python
manager.wait_for_service(max_retries=30)  # 起動を確認
```

**`print_connection_info() -> None`**
- Redis 接続情報を表示 (config 値を使用)

```python
manager.print_connection_info()
# 出力:
# 📦 Redis Connection:
#   Host: localhost
#   Port: 6379
#   CLI: redis-cli -p 6379
```

### CLI コマンド

#### redis_generate

**説明**: docker-compose.yml と redis.conf を生成

```bash
poetry run redis_generate
```

**生成ファイル**:
- `data/repom/docker-compose.generated.yml`
- `data/repom/redis_init/redis.conf`

#### redis_start

**説明**: Redis を起動

```bash
poetry run redis_start
```

**実行内容**:
1. `redis_generate` で環境を生成
2. `docker-compose up -d` で起動
3. `redis-cli ping` で健全性確認

#### redis_stop

**説明**: Redis を停止

```bash
poetry run redis_stop
```

#### redis_remove

**説明**: Redis を削除（完全リセット）

```bash
poetry run redis_remove
```

---

## 環境設定

### 環境変数での設定

#### REDIS_PORT

Redis のポート番号を指定

```bash
# .env ファイル
REDIS_PORT=6380
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=secret123
REDIS_DB=0

# または、コマンド実行時に指定
REDIS_PORT=6380 poetry run redis_start
```

#### その他の環境変数

- `REDIS_HOST`: Redis ホスト（デフォルト: `localhost`）
- `REDIS_PASSWORD`: Redis パスワード（オプション）
- `REDIS_DB`: Redis データベース番号（デフォルト: `0`）

### Config クラスでの設定

RepomConfig を継承して Redis 設定をカスタマイズできます：

```python
# repom/config.py (Issue #042 実装)

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RedisContainerConfig:
    """Redis コンテナ設定"""
    container_name: str = "repom_redis"
    volume_name: str = "repom_redis_data"
    image: str = "redis:7-alpine"
    
    def get_container_name(self) -> str:
        return self.container_name
    
    def get_volume_name(self) -> str:
        return self.volume_name

@dataclass
class RedisConfig:
    """Redis 接続設定"""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    container: RedisContainerConfig = field(default_factory=RedisContainerConfig)

class RepomConfig:
    redis: RedisConfig = field(default_factory=RedisConfig)
```

**使用例**:

```python
from repom.config import config

# Redis 接続情報を取得
print(config.redis.host)           # localhost
print(config.redis.port)           # 6379
print(config.redis.password)       # None
print(config.redis.db)             # 0

# コンテナ設定を取得
print(config.redis.container.get_container_name())  # repom_redis
print(config.redis.container.get_volume_name())      # repom_redis_data
print(config.redis.container.image)                  # redis:7-alpine
```

**外部プロジェクトでのカスタマイズ**:

```python
# mine_py/src/mine_py/config.py
from repom.config import RepomConfig, RedisConfig, RedisContainerConfig

class MinePyConfig(RepomConfig):
    def __init__(self):
        super().__init__()
        
        # Redis 設定を上書き
        self.redis = RedisConfig(
            host="redis.example.com",
            port=6380,
            password="secret",
            db=1,
            container=RedisContainerConfig(
                container_name="mine_py_redis",
                volume_name="mine_py_redis_data",
                image="redis:7-alpine"
            )
        )
```

---

## RedisConfig 設定ガイド

Issue #042 で実装された `RedisConfig` と `RedisContainerConfig` クラスについて詳しく説明します。

### RedisContainerConfig

Docker コンテナに関する設定を管理します：

```python
config.redis.container.container_name   # "repom_redis"
config.redis.container.volume_name      # "repom_redis_data"
config.redis.container.image            # "redis:7-alpine"
```

**メソッド**:

- `get_container_name() -> str`: コンテナ名を取得
- `get_volume_name() -> str`: ボリューム名を取得

### RedisConfig

Redis 接続とコンテナ設定を統一的に管理します：

**属性**:

| 属性 | 型 | デフォルト | 説明 |
|-----|-----|---------|------|
| `host` | str | `"localhost"` | Redis ホスト |
| `port` | int | `6379` | Redis ポート |
| `password` | Optional[str] | `None` | Redis パスワード |
| `db` | int | `0` | Redis DB 番号 |
| `container` | RedisContainerConfig | (デフォルト) | コンテナ設定 |

**例**: ローカル開発とプロダクション環境の切り分け

```python
# 開発環境
config_dev = RedisConfig(
    host="localhost",
    port=6379,
    db=0
)

# プロダクション環境
config_prod = RedisConfig(
    host="redis.prod.example.com",
    port=6380,
    password="prod_secret",
    db=1,
    container=RedisContainerConfig(
        container_name="prod_redis",
        volume_name="prod_redis_data",
        image="redis:7-alpine"
    )
)
```

---

## トラブルシューティング

### 問題: "Port 6379 is already in use"

**原因**: 別のサービスが Redis ポートを使用中

**解決策 1: 別のポートを指定**
```bash
REDIS_PORT=6380 poetry run redis_start
```

**解決策 2: 既存の Redis を確認・停止**
```bash
# Redis を探す
docker ps | grep redis

# 既存の Redis を停止
docker stop <container_id>
```

### 問題: "docker: command not found"

**原因**: Docker Desktop がインストールされていない

**解決策**: Docker Desktop をインストール
- Windows: [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- Mac: [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)

### 問題: "redis-cli: command not found"

**原因**: redis-cli が PATH に含まれていない

**解決策**: Docker 経由で実行
```bash
docker exec -it repom_redis redis-cli
```

### 問題: "Compose file not found"

**原因**: `redis_generate` を実行していない

**解決策**:
```bash
poetry run redis_generate  # 最初に実行
poetry run redis_start     # その後、起動
```

---

## Redis コマンドリファレンス

### よく使うコマンド

**キーの操作**
```bash
redis-cli

# キーを設定
SET mykey myvalue

# キーを取得
GET mykey

# キーを削除
DEL mykey

# すべてのキーを表示
KEYS *

# キーが存在するか確認
EXISTS mykey
```

**有効期限の設定**
```bash
# 10秒で自動削除
SETEX mykey 10 myvalue

# 有効期限を設定（秒）
EXPIRE mykey 10

# 有効期限を確認（秒）
TTL mykey
```

**リスト操作**
```bash
# リストに追加
LPUSH mylist value1

# リストを取得
LRANGE mylist 0 -1
```

**キャッシュ削除**
```bash
# すべてのキーを削除
FLUSHDB

# すべてのデータベースをクリア
FLUSHALL
```

### Redis CLI の起動

```bash
# Docker 経由での接続
docker exec -it repom_redis redis-cli

# ホストの redis-cli を使用
redis-cli -p 6379

# リモート先に接続
redis-cli -h <host> -p <port>
```

---

## 複数プロジェクトでの並行開発（CONFIG_HOOK）

repom をベースとする複数のプロジェクト（mine-py, fast-domain など）を同時に開発する場合、CONFIG_HOOK を使ってプロジェクトごとに独立した Redis 環境を構築できます。

### 設定例: fast-domain プロジェクト

```python
# fast_domain/config.py
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
    # **重要**: Docker Compose プロジェクト名を設定（コンテナ名の prefix）
    config.project_name = "fast_domain"
    
    # ポートをずらす（repom: 6379, fast_domain: 6381）
    config.redis.port = 6381
    
    return config
```

```bash
# fast_domain/.env
CONFIG_HOOK=fast_domain.config:hook_config
```

**重要**: `config.project_name` を設定することで、Docker Compose のプロジェクト名が変わり、コンテナ名の衝突が防げます。

### 起動

```powershell
# repom プロジェクト（project_name = "repom"）
cd repom
poetry run redis_start
# → Container: repom-redis-1, Port: 6379

# fast-domain プロジェクト（project_name = "fast_domain"）同時起動可能
cd fast-domain
poetry run redis_start
# → Container: fast_domain-redis-1, Port: 6381
```

### 接続

```python
# repom プロジェクト
import redis
r = redis.Redis(host='localhost', port=6379)

# fast-domain プロジェクト
import redis
r = redis.Redis(host='localhost', port=6381)
```

---

## PostgreSQL との比較

| 項目 | PostgreSQL | Redis |
|-----|-----------|-------|
| **コンテナ名** | repom_postgres | repom_redis |
| **ポート** | 5432 | 6379 |
| **データ型** | テーブル | キー-バリュー |
| **初期化** | SQL（DB 作成） | redis.conf（設定） |
| **起動確認** | pg_isready | redis-cli ping |
| **CLI コマンド** | postgres_* | redis_* |

---

## 実装例

### 簡単なキャッシュ

```python
import redis
from datetime import timedelta

def cache_user_data(user_id: int, user_data: dict):
    """ユーザーデータをキャッシュに保存"""
    r = redis.Redis(host='localhost', port=6379)
    r.setex(
        f'user:{user_id}',
        timedelta(hours=1),
        str(user_data)
    )

def get_cached_user(user_id: int):
    """キャッシュからユーザーデータを取得"""
    r = redis.Redis(host='localhost', port=6379)
    return r.get(f'user:{user_id}')
```

### セッション管理

```python
import redis
import json

class SessionManager:
    def __init__(self, host='localhost', port=6379):
        self.redis = redis.Redis(host=host, port=port)
    
    def save_session(self, session_id: str, data: dict, ttl: int = 3600):
        """セッションを保存"""
        self.redis.setex(
            f'session:{session_id}',
            ttl,
            json.dumps(data)
        )
    
    def get_session(self, session_id: str):
        """セッションを取得"""
        data = self.redis.get(f'session:{session_id}')
        return json.loads(data) if data else None
    
    def delete_session(self, session_id: str):
        """セッションを削除"""
        self.redis.delete(f'session:{session_id}')
```

---

## 参考資料

- [Redis 公式ドキュメント](https://redis.io/documentation)
- [redis-py](https://redis-py.readthedocs.io/)
- [Docker Manager ガイド](../features/docker_manager_guide.md)
- [Issue #042: Redis 設定管理と repom_info 統合](../../issue/completed/042_redis_config_and_repom_info_integration.md)
- [Issue #041: Redis Docker 統合](../../issue/completed/041_redis_docker_integration.md)
- [Issue #040: Docker 管理基盤](../../issue/completed/040_docker_management_base_infrastructure.md)

---

**作成者**: GitHub Copilot  
**最終更新**: 2026-02-23
