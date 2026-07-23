"""Minimal consumer-owned CONFIG_HOOK used by the external-project fixture."""
from pathlib import Path
from typing import Any


def hook_config(config: Any) -> Any:
    """Apply an unrelated consumer setting and return the same config."""
    config.root_path = str(Path(__file__).resolve().parents[2])
    return config
