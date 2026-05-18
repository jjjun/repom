"""Backward-compatible config hook exports from :mod:`basekit`."""

from basekit.config_hook import (
    Config,
    ConfigHookLoadError,
    get_config_from_hook,
    load_hook_function,
)

__all__ = [
    "Config",
    "ConfigHookLoadError",
    "get_config_from_hook",
    "load_hook_function",
]
