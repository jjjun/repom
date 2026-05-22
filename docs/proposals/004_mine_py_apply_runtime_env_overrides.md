# Proposal #004: mine-py should apply repom runtime env override helpers

## Metadata

| Item | Value |
|------|---|
| ID | 004 |
| Target project / package | mine-py |
| Type | migration |
| Status | draft |
| Created | 2026-05-22 |
| Updated | 2026-05-22 |

---

## Background

repom now provides runtime environment override helpers for database, PostgreSQL,
pgAdmin, Redis, and SQLite settings under `repom.config_hooks/`.

mine-py uses repom through a project-level `CONFIG_HOOK`. repom can provide the
helpers and documentation, but mine-py must decide which runtime env variables
are accepted and call the helpers after setting mine-py defaults.

---

## Current State And Problem

mine-py commonly needs environment-specific database and service settings:

- local development ports can differ from repom defaults
- CI may inject `DATABASE_URL` / `REPOM_DATABASE_URL`
- production-like environments may inject PostgreSQL and Redis credentials
- tests may need file-backed SQLite through env

Without explicit helper calls in mine-py's hook, these env values can be ignored
or reimplemented locally.

---

## Proposed Change

Update mine-py's repom config hook to call the shared helpers at the end:

```python
from repom.config_hooks.database import apply_database_env_overrides
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides
from repom.config_hooks.postgres import apply_postgres_env_overrides
from repom.config_hooks.redis import apply_redis_env_overrides
from repom.config_hooks.sqlite import apply_sqlite_env_overrides


def hook_config(config):
    # mine-py defaults first
    config.db_name = "mine_py"
    config.model_locations = ["mine_py.models"]
    config.allowed_package_prefixes = {"mine_py.", "repom."}
    config.postgres.container.container_name = "mine_py_postgres"
    config.redis.container.container_name = "mine_py_redis"

    # env overrides last
    apply_database_env_overrides(config)
    apply_postgres_env_overrides(config)
    apply_pgadmin_env_overrides(config)
    apply_redis_env_overrides(config)
    apply_sqlite_env_overrides(config)
    return config
```

Update mine-py's `.env.example`, developer setup docs, and CI docs to describe
which variables are supported.

---

## Expected Effect

mine-py keeps its project-specific defaults in code while allowing deployment,
CI, and local `.env` values to override sensitive or environment-specific
runtime settings without duplicating parsing logic.

---

## repom Follow-Up

- [x] Add database runtime env helper
- [x] Expand Redis runtime env helper
- [x] Add SQLite runtime env helper
- [x] Document helper call order in repom
- [ ] Delete this proposal after mine-py adopts or rejects the change

---

## Related Files

- `repom/config_hooks/database.py`
- `repom/config_hooks/postgres.py`
- `repom/config_hooks/pgadmin.py`
- `repom/config_hooks/redis.py`
- `repom/config_hooks/sqlite.py`
- mine-py: config hook module
- mine-py: `.env.example`
- mine-py: developer setup / CI documentation

---

## Discussion Log

### 2026-05-22 - repom

- repom introduced broader runtime env override helpers.
- mine-py still needs an explicit hook/doc update because its defaults live
  outside this repository.

---

## Decision

Pending mine-py follow-up.
