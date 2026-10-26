"""CONFIG_HOOK whose module imports repom.alembic while repom.config loads.

Importing repom.alembic.constants runs repom/alembic/__init__.py, so this hook
fails ``import repom`` if anything in that package imports repom.config at
module level (repom#291).
"""

from repom.alembic.constants import SCRIPT_LOCATION
from repom.config_hook import hook_config as repom_hook_config


def hook_config(config):
    config = repom_hook_config(config)
    config.alembic_script_location = SCRIPT_LOCATION
    return config
