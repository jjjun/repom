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
6. [トラブルシューティング](#トラブルシューティング)
7. [Redis CLI コマンド](#redisコマンドリファレンス)

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
- 戻り値: `"repom_redis"`

```python
from repom.redis.manage import RedisManager

manager = RedisManager()
print(manager.get_container_name())  # repom_redis
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

### REDIS_PORT

Redis のポート番号を指定

```bash
# .env ファイル
REDIS_PORT=6380

# または、コマンド実行時に指定
REDIS_PORT=6380 poetry run redis_start
```

### config.py での設定

```python
# repom/config.py

class RepomConfig:
    @property
    def redis_port(self) -> int:
        """Redis ポート（デフォルト: 6379）"""
        return int(getenv('REDIS_PORT', '6379'))
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
- [Issue #040: Docker 管理基盤](../../issue/completed/040_docker_management_base_infrastructure.md)
- [Issue #041: Redis Docker 統合](../../issue/completed/041_redis_docker_integration.md)

---

**作成者**: GitHub Copilot  
**最終更新**: 2026-02-23
