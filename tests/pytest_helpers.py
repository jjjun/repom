def _debug_logging_enabled(config):
    """Return whether explicit verbose output should enable DEBUG logging."""
    # pyproject.toml adds -q, so an explicit -vv produces effective verbosity 1.
    return config.option.verbose >= 1


# Upper bound for a child Python process started by a test. It only keeps a
# hung child from stalling the suite: a cold interpreter plus Alembic and model
# imports has exceeded 10 seconds on Windows while the full suite loads the
# machine, although the same child finishes in a few seconds on its own.
CHILD_PROCESS_TIMEOUT_SEC = 120
