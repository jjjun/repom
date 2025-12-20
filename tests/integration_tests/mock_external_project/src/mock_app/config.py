"""Mock config hook - simulates mine-py's hook_config function."""
from pathlib import Path
from dataclasses import dataclass


def hook_config(config: dataclass) -> dataclass:
    """Configuration hook function - simulates mine-py's CONFIG_HOOK.

    This mimics mine-py/src/mine_py/__init__.py:hook_config()
    """
    # Get the mock project root (simulates mine-py root)
    root_path = Path(__file__).parent.parent.parent

    config.root_path = str(root_path)

    if type(config).__name__ == 'RepomConfig':
        # Note: _alembic_versions_path no longer exists
        # Migration file location is controlled by alembic.ini only
        # Other custom settings can be configured here if needed
        pass

        print(f"[CONFIG_HOOK] Set alembic_versions_path to: {config._alembic_versions_path}")

    return config
