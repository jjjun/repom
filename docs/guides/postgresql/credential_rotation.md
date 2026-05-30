# PostgreSQL And pgAdmin Credential Rotation

repom can generate compose files with new PostgreSQL and pgAdmin credentials,
but existing Docker volumes keep the credentials that were initialized earlier.
Use the rotation helpers when you need to harden an existing local or
self-managed environment without deleting PostgreSQL data.

## PostgreSQL

Dry-run the SQL plan first:

```bash
uv run postgres_rotate_credentials --new-password "new-password"
```

Execute after reviewing the masked plan:

```bash
uv run postgres_rotate_credentials --new-password "new-password" --execute
```

If you are replacing the application role rather than only rotating the
password:

```bash
uv run postgres_rotate_credentials \
  --current-user repom \
  --current-password "old-password" \
  --new-user mine_py_app \
  --new-password "new-password" \
  --database mine_py \
  --database mine_py_dev \
  --database mine_py_test \
  --execute
```

The replacement-user path creates or updates the new role, grants database,
schema, table, sequence, and future default privileges, and does not drop the
old role.

## pgAdmin

repom uses pgAdmin's supported `setup.py update-user --password` path inside the
container. Dry-run first:

```bash
uv run pgadmin_rotate_password --new-password "new-password"
```

Execute after reviewing the masked command:

```bash
uv run pgadmin_rotate_password --new-password "new-password" --execute
```

If the update command is not usable for the installed pgAdmin image, recreate
only the pgAdmin volume after regenerating compose with the new
`PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` values:

```bash
uv run pgadmin_rotate_password --recreate-volume
uv run pgadmin_rotate_password --recreate-volume --execute --confirm-recreate-volume
uv run postgres_generate
uv run postgres_start
```

This fallback removes pgAdmin's own saved UI state, but it does not remove the
PostgreSQL data volume.

## Notes

- Rotation output masks passwords.
- PostgreSQL execution uses `PGPASSWORD` for the current password instead of
  embedding it in the command line.
- Review dry-run output before passing `--execute`.
