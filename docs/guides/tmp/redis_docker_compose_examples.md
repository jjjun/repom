# Redis Docker Compose Examples

## 基本的な Redis

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: fast_domain_redis
    ports:
      - "6379:6379"
    volumes:
      - fast_domain_redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  fast_domain_redis_data:
```

## Redis + Redis Insight（管理UI）

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: fast_domain_redis
    ports:
      - "6379:6379"
    volumes:
      - fast_domain_redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis-insight:
    image: redislabs/redisinsight:latest
    container_name: fast_domain_redis_insight
    ports:
      - "8001:8001"
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - redis_insight_data:/home/redisinsight

volumes:
  fast_domain_redis_data:
  redis_insight_data:
```

## Redis Cluster（将来の拡張）

```yaml
version: '3.8'

services:
  redis-1:
    image: redis:7-alpine
    container_name: fast_domain_redis_1
    ports:
      - "6379:6379"
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000
    volumes:
      - redis_node_1:/data

  redis-2:
    image: redis:7-alpine
    container_name: fast_domain_redis_2
    ports:
      - "6380:6379"
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000
    volumes:
      - redis_node_2:/data

  # ... more nodes

volumes:
  redis_node_1:
  redis_node_2:
```

---

## Python での使用例

### 接続

```python
import redis

# 標準接続
r = redis.Redis(host='localhost', port=6379, db=0)

# 接続確認
print(r.ping())  # True
```

### 基本操作

```python
# Set/Get
r.set('key', 'value')
print(r.get('key'))  # b'value'

# List
r.lpush('mylist', 'item1', 'item2')
print(r.lrange('mylist', 0, -1))  # [b'item2', b'item1']

# Hash
r.hset('myhash', 'field1', 'value1')
print(r.hget('myhash', 'field1'))  # b'value1'

# Set
r.sadd('myset', 'member1', 'member2')
print(r.smembers('myset'))  # {b'member1', b'member2'}

# Sorted Set
r.zadd('myzset', {'member1': 1, 'member2': 2})
print(r.zrange('myzset', 0, -1))  # [b'member1', b'member2']
```

---

## Redis CLI コマンド

```bash
# Docker コンテナへアクセス
docker exec -it fast_domain_redis redis-cli

# よく使うコマンド
PING                    # 接続確認
INFO                    # サーバー情報
DBSIZE                  # キー数確認
FLUSHDB                 # DB をクリア（注意！）
FLUSHALL                # すべての DB をクリア（危険！）
KEYS *                  # すべてのキーを表示
SAVE                    # ディスクにセーブ
BGSAVE                  # バックグラウンドセーブ
```

---

## パフォーマンスチューニング（オプション）

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: fast_domain_redis
    ports:
      - "6379:6379"
    volumes:
      - fast_domain_redis_data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    # リソース制限
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

`redis.conf` 例：
```
# メモリ上限
maxmemory 512mb
maxmemory-policy allkeys-lru

# 永続化
save 900 1      # 900秒以内に1つの変更があった場合セーブ
save 300 10     # 300秒以内に10の変更があった場合セーブ
save 60 10000   # 60秒以内に10000の変更があった場合セーブ

# ログ出力
loglevel notice
logfile ""
```

---

## トラブルシューティング

### Redis が起動しない

```bash
# ログ確認
docker logs fast_domain_redis

# ポート競合確認
netstat -tulpn | grep 6379
```

### 接続できない

```bash
# 接続テスト
redis-cli -h localhost -p 6379 ping

# Docker ネットワーク確認
docker network inspect bridge
```

### パフォーマンス問題

```bash
# INFO でメモリ使用量確認
docker exec fast_domain_redis redis-cli INFO memory

# キー数確認
docker exec fast_domain_redis redis-cli DBSIZE
```

---

**参考**:
- [Redis 公式ドキュメント](https://redis.io/documentation)
- [Docker Redis イメージ](https://hub.docker.com/_/redis)
- [RedisInsight](https://redis.com/redis-enterprise/redis-insight/)
