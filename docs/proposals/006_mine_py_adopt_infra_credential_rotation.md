# Proposal #006: mine-py should adopt repom infrastructure credential rotation

## Metadata

| Item | Value |
|------|---|
| ID | 006 |
| Target project / package | mine-py |
| Type | operations / security |
| Status | draft |
| Created | 2026-05-30 |
| Updated | 2026-05-30 |

---

## Background

mine-py proposed that repom should support data-preserving infrastructure
credential rotation for PostgreSQL, pgAdmin, and Redis before production
hardening.

repom accepted and completed that work in issue #76. repom now owns reusable
rotation commands and docs:

- `postgres_rotate_credentials`
- `pgadmin_rotate_password`
- `redis_rotate_password`
- `docs/guides/postgresql/credential_rotation.md`
- `docs/guides/redis/credential_rotation.md`

mine-py still owns its project-specific operational tasks, security gate,
environment files, and production setup guide.

---

## Current State And Problem

mine-py's stricter `maint.security-check` rejects well-known default
PostgreSQL and pgAdmin credentials and warns about unauthenticated Redis.
repom now provides the shared operations needed to fix those findings, but
mine-py still needs to wire them into its own workflow.

Updating environment variables alone is not enough for initialized Docker
volumes:

- PostgreSQL existing roles must be updated or replaced with grants.
- pgAdmin existing admin users must be updated, or only the pgAdmin volume must
  be recreated.
- Redis existing instances need runtime `CONFIG SET requirepass ...` and
  regenerated persisted config.

Without mine-py guidance, developers may pass the security check only for fresh
volumes or may delete PostgreSQL data while trying to rotate credentials.

---

## Proposed Change

Update mine-py to consume repom's credential rotation workflow instead of
carrying project-local infrastructure logic.

Recommended commands for mine-py docs or wrappers:

```bash
# PostgreSQL password-only dry-run
uv run postgres_rotate_credentials --new-password "new-password"

# PostgreSQL replacement role for mine-py
uv run postgres_rotate_credentials \
  --current-user repom \
  --current-password "old-password" \
  --new-user mine_py_app \
  --new-password "new-password" \
  --database mine_py \
  --database mine_py_dev \
  --database mine_py_test \
  --execute

# pgAdmin admin password
uv run pgadmin_rotate_password --new-password "new-password" --execute

# Redis password rotation
uv run redis_rotate_password \
  --old-password "old-password" \
  --new-password "new-password" \
  --execute
```

mine-py should update:

- `docs/guides/development/production_setup_guide.md` with the exact
  weak-to-strong credential migration sequence.
- `.env.example` or secret documentation to show the expected final
  `POSTGRES_USER`, `POSTGRES_PASSWORD`, `PGADMIN_DEFAULT_EMAIL`,
  `PGADMIN_DEFAULT_PASSWORD`, and `REDIS_PASSWORD` values.
- `maint.security-check` documentation so failures point to the rotation
  workflow.
- Optional thin task wrappers only where project naming prevents mistakes.

Recommended verification:

- Run the rotation commands in dry-run mode before `--execute`.
- Confirm PostgreSQL login using the final application role and password.
- Confirm pgAdmin login with the new admin password.
- Confirm Redis rejects unauthenticated `PING` and accepts authenticated
  `PING`.
- Run `maint.security-check` and verify default credential failures are gone.
- Start the mine-py runtime and worker with the final environment values.

---

## Expected Effect

- mine-py can harden existing local or self-managed infrastructure without
  deleting PostgreSQL data.
- The production setup guide can point to tested repom commands instead of
  manually described SQL or Docker volume operations.
- `maint.security-check` remains the gate, while repom remains the source of
  truth for infrastructure credential mechanics.
- No mine-py domain model or repository code needs to change.

---

## repom Follow-Up

- [x] Accept mine-py proposal #059 into repom issue #76.
- [x] Implement PostgreSQL credential rotation with dry-run SQL and password
  masking.
- [x] Implement pgAdmin password rotation and pgAdmin-volume-only fallback.
- [x] Make Redis generated config, health checks, and runtime rotation
  password-aware.
- [x] Add repom credential rotation documentation.
- [ ] Delete this proposal after mine-py adopts or rejects the change.

---

## Related Files

- `repom/postgres/credentials.py`
- `repom/redis/credentials.py`
- `repom/redis/manage.py`
- `docs/guides/postgresql/credential_rotation.md`
- `docs/guides/redis/credential_rotation.md`
- `docs/issues/completed/076_infra_credential_rotation.md`
- mine-py: `docs/proposals/059_repom_infra_credential_rotation.md`
- mine-py: `docs/issues/active/221_add_infra_credential_rotation_tasks.md`
- mine-py: `src/mine_py/tasks/maint.py`
- mine-py: `docs/guides/development/production_setup_guide.md`

---

## Discussion Log

### 2026-05-30 - repom

- repom reviewed mine-py proposal #059, accepted the repom-owned scope, and
  completed issue #76.
- mine-py still needs to adopt the completed repom commands in project docs,
  optional wrappers, and security-check guidance.

---

## Decision

Pending mine-py follow-up.
