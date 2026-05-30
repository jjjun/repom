---
id: 76
status: completed
priority: high
created: 2026-05-30
completed: 2026-05-30
title: Add data-preserving infrastructure credential rotation
---


# Issue #76: Add data-preserving infrastructure credential rotation

## Problem

repom owns the local and self-managed Docker helpers for PostgreSQL, pgAdmin,
and Redis, but those helpers mostly apply credentials only when generated files
or fresh Docker volumes are created.

Downstream projects need a safe hardening path from weak local defaults to
deployment-ready credentials without deleting PostgreSQL data. Updating
environment variables is not enough once existing Docker volumes have already
initialized PostgreSQL roles, pgAdmin users, or Redis runtime authentication.

Current gaps:

- PostgreSQL compose generation reads `POSTGRES_USER` and `POSTGRES_PASSWORD`,
  but existing roles are not rotated.
- pgAdmin compose generation reads `PGADMIN_DEFAULT_EMAIL` and
  `PGADMIN_DEFAULT_PASSWORD`, but existing pgAdmin volume users are not updated.
- Redis config hooks read `REDIS_PASSWORD`, but generated `redis.conf`,
  health checks, readiness checks, and runtime helpers do not authenticate or
  persist the password.

## Proposed Solution

Add repom-owned credential rotation support for the infrastructure surfaces
that repom already manages.

PostgreSQL should gain a planning and execution layer that can:

- Produce a dry-run SQL plan with passwords masked in logs and output.
- Rotate the password for the current role with `ALTER ROLE`.
- Optionally create a replacement role and grant access to configured
  databases, schemas, tables, sequences, and future default privileges.
- Refuse ambiguous destructive actions and avoid dropping the old role
  automatically.
- Use structured command construction and explicit arguments instead of shell
  string concatenation.

pgAdmin should gain the safest supported existing-volume password update path:

- Prefer an official pgAdmin CLI or supported internal command if one is stable.
- Update the configured admin user without touching the PostgreSQL volume.
- If no stable update path exists, document and automate a flow that recreates
  only the pgAdmin volume after regenerating compose with the new credentials.

Redis should make configured passwords effective for generated and existing
instances:

- Emit `requirepass <password>` or an ACL-equivalent setting in generated
  `redis.conf` when `config.redis.password` is set.
- Authenticate health checks and readiness checks when a password is configured.
- Add a helper that applies a new password to a running Redis instance, using
  the old password when present and persisting the generated config.
- Keep unauthenticated Redis behavior unchanged when no password is configured.

## Impact

- `repom/postgres/manage.py`
- `repom/postgres/config.py`
- `repom/postgres/__init__.py`
- `repom/redis/manage.py`
- `repom/redis/config.py`
- `repom/redis/init.template/redis.conf`
- `repom/redis/docker-compose.template.yml`
- `repom/config_hooks/postgres.py`
- `repom/config_hooks/pgadmin.py`
- `repom/config_hooks/redis.py`
- PostgreSQL and Redis guide documentation
- Unit and integration tests for generated compose/config and command planning

## Implementation Plan

1. Add small credential helper modules for PostgreSQL and Redis with explicit
   plan objects, password masking, and command builders.
2. Implement PostgreSQL dry-run SQL generation and execution for password-only
   rotation and non-destructive replacement-role grants.
3. Investigate pgAdmin's supported password update options and implement either
   the stable update path or a scoped pgAdmin-volume recreation helper.
4. Update Redis config generation to persist authentication, then update
   compose health checks and `RedisManager.wait_for_service()` to authenticate.
5. Add a Redis runtime password rotation helper that updates the running
   instance and regenerates the persisted config.
6. Document the weak-to-strong credential workflow and explicitly call out
   which volumes are preserved or recreated.

## Test Plan

- `uv run pytest tests/unit_tests/test_postgres_manage.py`
- `uv run pytest tests/unit_tests/test_redis_manage.py`
- `uv run pytest tests/unit_tests/test_config_hooks_postgres.py`
- `uv run pytest tests/unit_tests/test_config_hooks_pgadmin.py`
- `uv run pytest tests/unit_tests/test_config_hooks_redis.py`
- Add focused tests for PostgreSQL SQL planning, password masking, Redis
  generated config, authenticated Redis health checks, and pgAdmin fallback
  behavior.
- Where Docker is available, verify rotation against initialized PostgreSQL,
  pgAdmin, and Redis containers without deleting the PostgreSQL volume.

## Related Resources

- External proposal:
  `C:/Users/jj/Desktop/workspace_main/projects/mine-py/docs/proposals/059_repom_infra_credential_rotation.md`
- `docs/issues/completed/073_postgres_pgadmin_env_override_hooks.md`
- `docs/issues/completed/074_runtime_env_override_expansion.md`
- `docs/guides/postgresql/runtime_env_overrides.md`
- `docs/guides/redis/README.md`

**Completed**: 2026-05-30

## Completion Notes

- Added data-preserving credential rotation helpers for PostgreSQL, pgAdmin, and Redis with masked dry-run output and non-destructive defaults.
- Verification: `uv run pytest; issuekit validate`
