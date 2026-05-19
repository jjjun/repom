"""Feature-specific config module import tests."""

from repom.config import (
    PgAdminConfig,
    PgAdminContainerConfig,
    PostgresConfig,
    PostgresContainerConfig,
    RedisConfig,
    RedisContainerConfig,
    RepomConfig,
    SqliteConfig,
)
from repom.postgres.config import (
    PgAdminConfig as DirectPgAdminConfig,
    PgAdminContainerConfig as DirectPgAdminContainerConfig,
    PostgresConfig as DirectPostgresConfig,
    PostgresContainerConfig as DirectPostgresContainerConfig,
)
from repom.redis.config import RedisConfig as DirectRedisConfig
from repom.redis.config import RedisContainerConfig as DirectRedisContainerConfig
from repom.sqlite.config import SqliteConfig as DirectSqliteConfig


def test_config_re_exports_feature_config_classes():
    assert PostgresConfig is DirectPostgresConfig
    assert PostgresContainerConfig is DirectPostgresContainerConfig
    assert PgAdminConfig is DirectPgAdminConfig
    assert PgAdminContainerConfig is DirectPgAdminContainerConfig
    assert RedisConfig is DirectRedisConfig
    assert RedisContainerConfig is DirectRedisContainerConfig
    assert SqliteConfig is DirectSqliteConfig


def test_repom_config_uses_feature_config_instances():
    config = RepomConfig()

    assert isinstance(config.postgres, DirectPostgresConfig)
    assert isinstance(config.pgadmin, DirectPgAdminConfig)
    assert isinstance(config.redis, DirectRedisConfig)
    assert isinstance(config.sqlite, DirectSqliteConfig)
