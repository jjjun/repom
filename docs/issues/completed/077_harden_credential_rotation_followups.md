---
id: 77
status: completed
priority: high
created: 2026-05-30
completed: 2026-05-30
title: Harden credential rotation follow-ups
---


# Issue #77: Harden credential rotation follow-ups

## Problem

Downstream review of issue #76 found two credential rotation follow-ups that
should be fixed before downstream projects document the workflow as a production
hardening path.

First, `RedisCredentialRotationPlan.from_config()` treats an omitted
`old_password` as `config.redis.password`. That breaks the documented
unauthenticated-to-authenticated migration flow when the operator has already
set `REDIS_PASSWORD` to the final desired value. In that case repom tries to
authenticate to an unauthenticated Redis instance with the new password.

Second, printed output is masked, but some executed commands still place
secrets in process arguments. PostgreSQL currently uses `psql -c` with SQL that
contains the new password, pgAdmin uses `setup.py update-user --password`, and
Redis old-password authentication is passed through `docker exec -e
REDISCLI_AUTH=...`.

## Proposed Solution

Update the rotation helpers so omitted old credentials are not inferred from
final desired configuration and so new PostgreSQL passwords are not placed in
command arguments.

Redis:

- Treat `old_password=None` as currently unauthenticated.
- Keep `new_password=None` fallback at the CLI layer through
  `config.redis.password`.
- Require callers to pass `old_password` explicitly when Redis is already
  authenticated.
- Fix comments and docs so they do not imply `REDISCLI_AUTH` is hidden from
  process arguments.

PostgreSQL:

- Run SQL through stdin instead of `psql -c`.
- Keep `PGPASSWORD` for the current connection password.
- Ensure executed command tuples do not contain `plan.new_password`.
- Preserve masked dry-run output.

pgAdmin:

- Document the `setup.py update-user --password` process-argument limitation.
- Keep the pgAdmin-volume-only recreation fallback documented as the lower
  exposure path when update-user argument exposure is unacceptable.

## Impact

- `repom/redis/credentials.py`
- `repom/redis/manage.py`
- `repom/postgres/credentials.py`
- `docs/guides/redis/credential_rotation.md`
- `docs/guides/postgresql/credential_rotation.md`
- `tests/unit_tests/test_redis_credentials.py`
- `tests/unit_tests/test_postgres_credentials.py`

## Implementation Plan

1. Change Redis plan construction so `old_password` remains exactly what the
   caller passed.
2. Add Redis tests for unauthenticated enablement and explicit old-password
   rotation.
3. Change PostgreSQL command construction to omit `-c` and pass SQL to
   `subprocess.run(input=...)`.
4. Add PostgreSQL tests that executed command tuples do not contain the new
   password while stdin still carries the SQL.
5. Update credential rotation docs for Redis and pgAdmin limitations.

## Test Plan

- `uv run pytest tests/unit_tests/test_redis_credentials.py`
- `uv run pytest tests/unit_tests/test_postgres_credentials.py`
- `uv run pytest tests/unit_tests/test_redis_manage.py`
- `uv run pytest tests/unit_tests/test_redis_manager.py`
- `uv run ruff check repom tests/unit_tests/test_postgres_credentials.py tests/unit_tests/test_redis_credentials.py`
- `issuekit validate`

## Related Resources

- External proposal:
  `C:/Users/jj/Desktop/workspace_main/projects/mine-py/docs/proposals/062_repom_harden_credential_rotation_followups.md`
- `docs/issues/completed/076_infra_credential_rotation.md`
- `repom/redis/credentials.py`
- `repom/postgres/credentials.py`

**Completed**: 2026-05-30

## Completion Notes

- Fixed Redis old-password handling, moved PostgreSQL SQL execution to stdin, and documented pgAdmin process-argument limitations.
- Verification: `uv run pytest; uv run ruff check repom tests/unit_tests/test_postgres_credentials.py tests/unit_tests/test_redis_credentials.py; issuekit validate`
