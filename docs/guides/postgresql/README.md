# PostgreSQL ガイド

repom の PostgreSQL 関連ガイドです。

## 📋 ガイド一覧

- **[postgresql_setup_guide.md](postgresql_setup_guide.md)** - PostgreSQL セットアップガイド

## 🔗 関連リソース

- **Docker Manager ガイド**: [../features/docker_manager_guide.md](../features/docker_manager_guide.md)
  - Docker コンテナ管理の基盤
  - Redis との統一インターフェース

- **Issue #038**: PostgreSQL コンテナ設定のカスタマイズ対応
  - [完了済み](../../issue/completed/038_postgresql_container_customization.md)

- **Issue #040**: Docker 管理基盤
  - [完了済み](../../issue/completed/040_docker_management_base_infrastructure.md)

## 🚀 クイックスタート

```bash
# PostgreSQL 環境を生成
uv run postgres_generate

# PostgreSQL を起動
uv run postgres_start

# PostgreSQL に接続
psql -U repom -d repom_dev -h localhost -p 5432

# PostgreSQL を停止
uv run postgres_stop
```

## 📦 環境変数

```bash
# PostgreSQL ポートをカスタマイズ（デフォルト: 5432）
PG_HOST_PORT=5433

# pgAdmin を有効化（デフォルト: false）
# docs/guides/postgresql/postgresql_setup_guide.md を参照
```

---

**参考**: [Redis ガイド](../redis/README.md) - Redis 環境管理
