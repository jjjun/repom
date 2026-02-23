# Redis ガイド

repom の Redis 関連ガイドです。

## 📋 ガイド一覧

- **[redis_manager_guide.md](redis_manager_guide.md)** - Redis Manager の完全ガイド
  - セットアップとクイックスタート
  - API リファレンス
  - 環境設定
  - トラブルシューティング
  - 実装例（キャッシュ、セッション管理）

## 🔗 関連リソース

- **Docker Manager ガイド**: [../features/docker_manager_guide.md](../features/docker_manager_guide.md)
  - Docker コンテナ管理の基盤
  - PostgreSQL との統一インターフェース

- **Issue #042**: Redis 設定管理と repom_info 統合
  - [完了済み](../../issue/completed/042_redis_config_and_repom_info_integration.md)
  - RedisConfig + RedisContainerConfig クラス、config 統合

- **Issue #041**: Redis Docker 統合
  - [完了済み](../../issue/completed/041_redis_docker_integration.md)

- **Issue #040**: Docker 管理基盤
  - [完了済み](../../issue/completed/040_docker_management_base_infrastructure.md)

## 🚀 クイックスタート

```bash
# Redis 環境を生成
poetry run redis_generate

# Redis を起動
poetry run redis_start

# Redis CLI で接続
docker exec -it repom_redis redis-cli

# Redis を停止
poetry run redis_stop
```

## 📦 設定

### 環境変数でのカスタマイズ

```bash
# Redis ポートをカスタマイズ（デフォルト: 6379）
REDIS_PORT=6380
```

### config でのカスタマイズ

RepomConfig の `redis` フィールドで詳細設定が可能です：

```python
from repom.config import config

# Redis 設定を確認
print(config.redis.port)  # 6379
print(config.redis.host)  # localhost
print(config.redis.container.get_container_name())  # repom_redis
print(config.redis.container.get_volume_name())  # repom_redis_data
```

Details:
- **redis_config_guide.md** - RedisConfig クラスの詳細ガイド

---

## 🔍 Redis 設定情報の表示

`repom_info` コマンドで Redis 設定と接続状態を確認できます：

```bash
poetry run repom_info
```

**出力例**:
```
[Redis Configuration]
  Host              : localhost
  Port              : 6379
  Container Name    : repom_redis
  Image             : redis:7-alpine

[Redis Connection Test]
  Status            : ✓ Connected
```

---

**参考**: 
- [PostgreSQL ガイド](../postgresql/README.md) - PostgreSQL 環境管理
- [Config Display Command (repom_info)](../features/config_display_command.md)
