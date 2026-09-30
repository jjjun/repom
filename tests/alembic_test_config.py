"""Configuration hook for Alembic subprocess tests."""

import os

from repom.config_hooks.sqlite import apply_sqlite_env_overrides


def hook_config(config):
    config.root_path = os.environ["REPOM_TEST_ROOT"]
    config.db_type = "sqlite"
    config.model_locations = ["repom.examples.models"]
    config.allowed_package_prefixes = {"repom."}
    apply_sqlite_env_overrides(config)
    return config
