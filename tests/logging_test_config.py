"""Configuration hook for logging import side-effect subprocess tests."""

import os
from pathlib import Path


def hook_config(config):
    root_path = Path(os.environ["REPOM_LOGGING_TEST_ROOT"])
    config.root_path = str(root_path)
    config.data_path = str(root_path / "data")
    config.log_path = str(root_path / "logs")
    config.db_backup_path = str(root_path / "backups")
    config.master_data_path = str(root_path / "data_master")
    config.db_url = "sqlite:///:memory:"
    if not os.environ.get("BASEKIT_NO_SIDE_EFFECTS"):
        config.auto_create_dirs = False
    return config
