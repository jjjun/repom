# Proposal #005: fast-domain should adopt repom infrastructure credential rotation

## Metadata

| Item | Value |
|------|---|
| ID | 005 |
| Target project / package | fast-domain |
| Type | operations / security |
| Status | draft |
| Created | 2026-05-30 |
| Updated | 2026-05-30 |

---

## Background

repom issue #76 added data-preserving credential rotation support for the
local and self-managed infrastructure surfaces that repom owns:

- PostgreSQL credential planning and execution through
  `postgres_rotate_credentials`
- pgAdmin admin password rotation through `pgadmin_rotate_password`
- Redis password persistence, authenticated health checks, and runtime
  rotation through `redis_rotate_password`

fast-domain uses repom infrastructure helpers, but project-specific operational
docs, task wrappers, and deployment gates live in fast-domain. repom cannot
decide how fast-domain names its local containers, secrets, CI checks, or
deployment runbooks.

---

## Current State And Problem

Changing `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`PGADMIN_DEFAULT_PASSWORD`, or `REDIS_PASSWORD` in environment files is enough
for newly generated files and fresh Docker volumes, but it is not by itself a
complete rotation workflow for initialized services.

After fast-domain has existing Docker volumes:

- PostgreSQL roles keep the password from initialization until `ALTER ROLE` or
  replacement-role grants are applied.
- pgAdmin keeps its admin user in the pgAdmin volume until the user is updated
  or only the pgAdmin volume is recreated.
- Redis needs both runtime `CONFIG SET requirepass ...` and regenerated
  `redis.conf` so the password survives restart.

Without a fast-domain runbook or thin wrappers, operators may either rotate only
environment values or delete the wrong Docker volume.

---

## Proposed Change

Update fast-domain to consume the new repom rotation commands.

Recommended project-level tasks or docs:

```bash
# PostgreSQL password-only dry-run
uv run postgres_rotate_credentials --new-password "new-password"

# PostgreSQL password-only execution
uv run postgres_rotate_credentials --new-password "new-password" --execute

# PostgreSQL replacement role
uv run postgres_rotate_credentials \
  --current-user repom \
  --current-password "old-password" \
  --new-user fast_domain_app \
  --new-password "new-password" \
  --database fast_domain \
  --database fast_domain_dev \
  --database fast_domain_test \
  --execute

# pgAdmin admin password
uv run pgadmin_rotate_password --new-password "new-password" --execute

# Redis runtime and persisted password rotation
uv run redis_rotate_password \
  --old-password "old-password" \
  --new-password "new-password" \
  --execute
```

fast-domain should document:

- Which role name is recommended for the application.
- Which database names should be passed to `--database`.
- Which `.env` or secret values must be updated before and after execution.
- That pgAdmin fallback recreation deletes only pgAdmin UI state, not
  PostgreSQL data.
- How to verify PostgreSQL login, pgAdmin login, Redis auth, and application
  startup after rotation.

If fast-domain has a local task runner, add thin wrappers only where they reduce
operator mistakes. The wrappers should call repom commands instead of
duplicating SQL, Docker, or Redis logic.

---

## Expected Effect

- fast-domain can harden existing local or self-managed infrastructure without
  deleting PostgreSQL data.
- Redis password support becomes an actual runtime setting for generated
  Redis containers.
- Rotation steps become repeatable, reviewable, and aligned with repom's
  password masking and dry-run behavior.
- fast-domain avoids carrying project-local implementations of PostgreSQL,
  pgAdmin, or Redis credential operations.

---

## repom Follow-Up

- [x] Add PostgreSQL credential rotation SQL planning and execution helpers.
- [x] Add pgAdmin password rotation and pgAdmin-volume-only fallback helpers.
- [x] Make generated Redis config and health checks password-aware.
- [x] Add Redis runtime password rotation helper.
- [x] Add repom docs for PostgreSQL, pgAdmin, and Redis credential rotation.
- [ ] Delete this proposal after fast-domain adopts or rejects the change.

---

## Related Files

- `repom/postgres/credentials.py`
- `repom/redis/credentials.py`
- `repom/redis/manage.py`
- `docs/guides/postgresql/credential_rotation.md`
- `docs/guides/redis/credential_rotation.md`
- `docs/issues/completed/076_infra_credential_rotation.md`
- fast-domain: config hook module
- fast-domain: `.env.example`
- fast-domain: deployment and local infrastructure documentation
- fast-domain: maintenance or security-check tasks, if present

---

## Discussion Log

### 2026-05-30 - repom

- repom completed issue #76 and now exposes reusable credential rotation
  commands.
- fast-domain still needs project-specific documentation, defaults, and optional
  wrappers because those choices live outside repom.

---

## Decision

Pending fast-domain follow-up.
