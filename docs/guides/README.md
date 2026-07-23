# repom guides

現行実装の使い方を機能別にまとめています。

## モデル

- [BaseModelAuto とスキーマ生成](model/base_model_auto_guide.md)
- [システムカラムとカスタム型](model/system_columns_and_custom_types.md)
- [Soft Delete](model/soft_delete_guide.md)

## Repository

- [BaseRepository 基礎](repository/base_repository_guide.md)
- [検索、filter、eager loading](repository/repository_advanced_guide.md)
- [FilterParams](repository/repository_filter_params_guide.md)
- [order_by](repository/order_by_guide.md)
- [セッション管理](repository/repository_session_patterns.md)
- [AsyncBaseRepository](repository/async_repository_guide.md)

## 設定と付加機能

- [CONFIG_HOOK](features/config_hook_guide.md)
- [モデル自動 import](features/auto_import_models_guide.md)
- [Alembic](features/alembic_migration_guide.md)
- [マスターデータ同期](features/master_data_sync_guide.md)
- [ロギング](features/logging_guide.md)
- [QueryAnalyzer](features/query_analyzer_guide.md)
- [Docker 管理の責務境界](features/docker_manager_guide.md)

## PostgreSQL / Redis

- [PostgreSQL](postgresql/README.md)
- [PostgreSQL runtime overrides](postgresql/runtime_env_overrides.md)
- [PostgreSQL credential rotation](postgresql/credential_rotation.md)
- [Redis](redis/README.md)
- [Redis credential rotation](redis/credential_rotation.md)

## テスト

- [Testing Guide](testing/testing_guide.md)
- [pytest fixture Guide](testing/fixture_guide.md)

公開 API の概要、インストール、CLI 一覧はルートの [README](../../README.md) を
参照してください。
