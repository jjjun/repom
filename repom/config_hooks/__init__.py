"""Config hook apply helpers for repom."""

from typing import Any

from repom.config_hooks.database import apply_database_env_overrides
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides
from repom.config_hooks.postgres import apply_postgres_env_overrides
from repom.config_hooks.redis import apply_redis_env_overrides
from repom.config_hooks.sqlite import apply_sqlite_env_overrides


def apply_repom_env_overrides(config: Any) -> None:
    """Apply all repom environment overrides in the canonical order."""
    apply_database_env_overrides(config)
    apply_postgres_env_overrides(config)
    apply_pgadmin_env_overrides(config)
    apply_redis_env_overrides(config)
    apply_sqlite_env_overrides(config)


__all__ = ["apply_repom_env_overrides"]
