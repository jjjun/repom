# repom ガイド

現行実装の使い方を機能別にまとめています。

## モデル

- [モデルガイド一覧](model/README.md)
- [システムカラムとカスタム型](model/system_columns_and_custom_types.md)
- [Soft Delete](model/soft_delete_guide.md)
- [ManyToManyMixin](model/many_to_many_guide.md)

## リポジトリ

- [リポジトリガイド一覧](repository/README.md)
- [BaseRepository 基礎](repository/base_repository_guide.md)
- [AsyncBaseRepository](repository/async_repository_guide.md)
- [検索、filter、eager loading](repository/repository_advanced_guide.md)
- [FilterParams](repository/repository_filter_params_guide.md)
- [order_by](repository/order_by_guide.md)
- [セッション管理](repository/repository_session_patterns.md)

## 設定と付加機能

- [機能ガイド一覧](features/README.md)
- [CONFIG_HOOK](features/config_hook_guide.md)
- [Alembic](features/alembic_migration_guide.md)
- [モデル自動 import](features/auto_import_models_guide.md)
- [マスターデータ同期](features/master_data_sync_guide.md)
- [バックアップ / リストア](features/backup_guide.md)
- [ロギング](features/logging_guide.md)
- [QueryAnalyzer](features/query_analyzer_guide.md)
- [Docker manager と Compose の責務境界](features/docker_manager_guide.md)
- [NUL byte の検証](features/nul_byte_validation.md)

## PostgreSQL / Redis

- [PostgreSQL ガイド一覧](postgresql/README.md)
- [PostgreSQL セットアップ](postgresql/postgresql_setup_guide.md)
- [PostgreSQL の実行時環境変数](postgresql/runtime_env_overrides.md)
- [PostgreSQL 認証情報のローテーション](postgresql/credential_rotation.md)
- [Redis ガイド一覧](redis/README.md)
- [Redis の設定と service lifecycle](redis/redis_manager_guide.md)
- [Redis 認証情報のローテーション](redis/credential_rotation.md)

## テスト

- [テストガイド一覧](testing/README.md)
- [テストガイド](testing/testing_guide.md)
- [pytest fixture ガイド](testing/fixture_guide.md)

公開 API の概要、インストール、CLI 一覧はルートの [README](../../README.md) を
参照してください。
