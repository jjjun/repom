# Mock external project

This fixture simulates a consumer that uses repom's Alembic environment while
storing its own revisions.

`alembic.ini` is the single source of truth:

```ini
[alembic]
script_location = %(here)s/../../../alembic
version_locations = %(here)s/alembic/versions
```

`%(here)s` is the directory containing this configuration file, so the fixture
does not depend on a username, drive letter, or checkout location. The
consumer's `CONFIG_HOOK` does not configure migration paths.

To verify the resolved paths:

```powershell
uv run python tests/integration_tests/mock_external_project/debug_migration_location.py
```

Migration files created with this configuration belong under
`tests/integration_tests/mock_external_project/alembic/versions`.
