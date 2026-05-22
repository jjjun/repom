# Proposal #003: fast-domain should apply repom runtime env override helpers

## Metadata

| Item | Value |
|------|---|
| ID | 003 |
| Target project / package | fast-domain |
| Type | migration |
| Status | implemented |
| Created | 2026-05-22 |
| Updated | 2026-05-22 |

---

## Background

repom now provides runtime environment override helpers for database, PostgreSQL,
pgAdmin, Redis, and SQLite settings under `repom.config_hooks/`.

fast-domain owns its project-specific defaults through `CONFIG_HOOK`. repom
cannot safely change fast-domain's hook from this repository, but fast-domain
needs to call the shared helpers after setting local defaults if environment
variables should override those defaults.

---

## Current State And Problem

Older guidance covered only `REDIS_PORT` via
`apply_redis_env_overrides(config)`. The helper now covers more Redis fields,
and additional helpers exist for `DATABASE_URL` / `DB_TYPE`, PostgreSQL,
pgAdmin, and SQLite.

If fast-domain does not call these helpers, CI and local `.env` values such as
`REPOM_DATABASE_URL`, `POSTGRES_PORT`, `REDIS_HOST`, or
`SQLALCHEMY_ECHO=true` will not consistently override hard-coded hook defaults.

---

## Proposed Change

Update fast-domain's config hook to call the repom helpers at the end:

```python
from repom.config_hooks.database import apply_database_env_overrides
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides
from repom.config_hooks.postgres import apply_postgres_env_overrides
from repom.config_hooks.redis import apply_redis_env_overrides
from repom.config_hooks.sqlite import apply_sqlite_env_overrides


def hook_config(config):
    # fast-domain defaults first
    config.db_name = "fast_domain"
    config.postgres.container.container_name = "fast_domain_postgres"
    config.redis.container.container_name = "fast_domain_redis"
    config.redis.port = 6381

    # env overrides last
    apply_database_env_overrides(config)
    apply_postgres_env_overrides(config)
    apply_pgadmin_env_overrides(config)
    apply_redis_env_overrides(config)
    apply_sqlite_env_overrides(config)
    return config
```

Update fast-domain docs and `.env.example` to list the supported override
variables that the project wants to expose.

---

## Expected Effect

fast-domain keeps deterministic project defaults while allowing explicit env
values from local development, CI, and deployment secrets to win.

---

## repom Follow-Up

- [x] Add database runtime env helper
- [x] Expand Redis runtime env helper
- [x] Add SQLite runtime env helper
- [x] Document helper call order in repom
- [x] fast-domain adopted the change
- [ ] Delete this proposal if the team wants to remove implemented cross-repo notes

---

## Related Files

- `repom/config_hooks/database.py`
- `repom/config_hooks/postgres.py`
- `repom/config_hooks/pgadmin.py`
- `repom/config_hooks/redis.py`
- `repom/config_hooks/sqlite.py`
- fast-domain: config hook module
- fast-domain: `.env.example`
- fast-domain: config/runtime documentation

---

## Discussion Log

### 2026-05-22 - repom

- repom introduced broader runtime env override helpers.
- fast-domain still needs an explicit hook/doc update because its defaults live
  outside this repository.

### 2026-05-22 - fast-domain

- fast-domain updated `fast_domain.config_hook:hook_config` to call the repom
  database, PostgreSQL, pgAdmin, Redis, and SQLite runtime env override helpers
  after local defaults.
- fast-domain updated config hook docs and added `.env.example` entries for the
  supported runtime env overrides.

---

## Decision

Implemented in fast-domain.
