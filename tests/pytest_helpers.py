def _debug_logging_enabled(config):
    """Return whether explicit verbose output should enable DEBUG logging."""
    # pyproject.toml adds -q, so an explicit -vv produces effective verbosity 1.
    return config.option.verbose >= 1


# Upper bound for a child Python process started by a test. It only keeps a
# hung child from stalling the suite: a cold interpreter plus Alembic and model
# imports has exceeded 10 seconds on Windows while the full suite loads the
# machine, although the same child finishes in a few seconds on its own.
CHILD_PROCESS_TIMEOUT_SEC = 120


def read_standard_sql_literal(sql, start):
    """Parse the string literal opening at ``sql[start]`` as PostgreSQL does with
    ``standard_conforming_strings = on``.

    Only a doubled single quote is an escape; a backslash is an ordinary
    character. Return the literal's value and the index just past its closing
    quote.
    """
    assert sql[start] == "'"
    value = []
    index = start + 1
    while True:
        char = sql[index]
        if char == "'":
            if sql[index + 1 : index + 2] != "'":
                return "".join(value), index + 1
            index += 1
        value.append(char)
        index += 1
