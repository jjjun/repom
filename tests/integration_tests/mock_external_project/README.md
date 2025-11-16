"""README for Mock External Project

This directory simulates an external project (like mine-py) that uses repom as a submodule.

## Structure

```
mock_external_project/
├── alembic/
│   ├── versions/          # ← Migration files should be created HERE
│   └── .gitkeep
├── src/
│   └── mock_app/
│       ├── __init__.py
│       └── config.py      # CONFIG_HOOK implementation
├── alembic.ini            # Points to repom/alembic/env.py
├── .env                   # CONFIG_HOOK=mock_app.config:hook_config
├── debug_migration_location.py
└── README.md
```

## Purpose

Reproduce the issue where:
1. CONFIG_HOOK correctly sets `alembic_versions_path` to `mock_external_project/alembic/versions/`
2. But `alembic revision --autogenerate` creates files in `repom/alembic/versions/` instead

## How to Use

### 1. Debug Configuration

```powershell
cd tests/integration_tests/mock_external_project
poetry run python debug_migration_location.py
```

This will verify that CONFIG_HOOK is working correctly.

### 2. Reproduce the Issue

```powershell
cd tests/integration_tests/mock_external_project

# Set environment
$env:CONFIG_HOOK='mock_app.config:hook_config'
$env:EXEC_ENV='test'
$env:PYTHONPATH='src;' + $env:PYTHONPATH

# Generate migration file
poetry run alembic revision --autogenerate -m "test migration"
```

### 3. Check Result

The migration file should be created in:
- ✅ Expected: `mock_external_project/alembic/versions/XXXXX_test_migration.py`
- ❌ Bug: `repom/alembic/versions/XXXXX_test_migration.py`

## Expected Behavior

When using CONFIG_HOOK:
1. `MineDbConfig._alembic_versions_path` is set to custom path
2. `env.py` passes this to `context.configure(version_locations=...)`
3. Alembic creates migration files in the custom path

## Actual Behavior (Bug)

Migration files are created in `script_location/versions/` regardless of `version_locations` setting.

This indicates that Alembic's `revision --autogenerate` command does not respect the `version_locations` parameter when creating new migration files.
