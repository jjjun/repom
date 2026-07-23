# Feature guides

## Configuration and database lifecycle

- [Configuration hooks](config_hook_guide.md)
- [Alembic migrations](alembic_migration_guide.md)
- [Model discovery](auto_import_models_guide.md)
- [Master-data synchronization](master_data_sync_guide.md)

## Diagnostics and infrastructure

- [Logging](logging_guide.md)
- [QueryAnalyzer](query_analyzer_guide.md)
- [Docker responsibility boundary](docker_manager_guide.md)
- [Compose generation](docker_compose_guide.md)
- [Generic discovery responsibility boundary](discovery_guide.md)

Generic package discovery and Docker/Compose orchestration are implemented by
basekit. These pages describe repom's integration points and service-specific
behavior instead of duplicating basekit's API reference.
