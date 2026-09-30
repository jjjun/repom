"""Keep the test session's RepomConfig paths inside a temporary root."""

import os
from pathlib import Path

from basekit.config_hook import load_hook_function


def hook_config(config):
    """Apply the requested project hook, then isolate its filesystem paths."""
    test_root = Path(os.environ['REPOM_TEST_ROOT'])
    test_data_path = test_root / 'data' / 'repom'
    config.root_path = str(test_root)
    config.data_path = str(test_data_path)
    config.log_path = str(test_data_path / 'logs')
    config.db_backup_path = str(test_data_path / 'backups')
    config.master_data_path = str(test_root / 'data_master')
    config.sqlite.db_path = str(test_data_path)

    original_hook = os.environ.get('REPOM_TEST_ORIGINAL_CONFIG_HOOK')
    if original_hook and original_hook != os.environ.get('CONFIG_HOOK'):
        config = load_hook_function(
            original_hook, source='REPOM_TEST_ORIGINAL_CONFIG_HOOK'
        )(config)

    config.root_path = os.environ['REPOM_TEST_ROOT']
    config.data_path = None
    config.log_path = None
    config.db_backup_path = None
    config.master_data_path = None
    return config
