"""Feature-specific config module import tests."""

import pytest

from repom.config import RepomConfig
from repom.postgres.config import (
    PgAdminConfig as DirectPgAdminConfig,
    PgAdminContainerConfig as DirectPgAdminContainerConfig,
    PostgresConfig as DirectPostgresConfig,
    PostgresContainerConfig as DirectPostgresContainerConfig,
)
from repom.redis.config import RedisConfig as DirectRedisConfig
from repom.redis.config import RedisContainerConfig as DirectRedisContainerConfig
from repom.sqlite.config import SqliteConfig as DirectSqliteConfig


def test_config_no_longer_re_exports_feature_config_classes():
    with pytest.raises(ImportError):
        from repom.config import RedisContainerConfig  # noqa: F401

    import repom.config as config_module

    assert config_module.__all__ == ["RepomConfig", "config"]


def test_repom_config_uses_feature_config_instances():
    config = RepomConfig()

    assert isinstance(config.postgres, DirectPostgresConfig)
    assert isinstance(config.pgadmin, DirectPgAdminConfig)
    assert isinstance(config.redis, DirectRedisConfig)
    assert isinstance(config.sqlite, DirectSqliteConfig)
