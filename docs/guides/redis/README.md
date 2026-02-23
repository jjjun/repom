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

## 📦 環境変数

```bash
# Redis ポートをカスタマイズ（デフォルト: 6379）
REDIS_PORT=6380
```

---

**参考**: [PostgreSQL ガイド](../postgresql/README.md) - PostgreSQL 環境管理
