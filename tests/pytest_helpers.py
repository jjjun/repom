def _debug_logging_enabled(config):
    """Return whether explicit verbose output should enable DEBUG logging."""
    # pyproject.toml adds -q, so an explicit -vv produces effective verbosity 1.
    return config.option.verbose >= 1
