# PostgreSQL And pgAdmin Credential Rotation

repom can generate compose files with new PostgreSQL and pgAdmin credentials,
but existing Docker volumes keep the credentials that were initialized earlier.
Use the rotation helpers when you need to harden an existing local or
self-managed environment without deleting PostgreSQL data.

## PostgreSQL

Dry-run the SQL plan first:

```bash
printf '%s\n' 'new-password' | uv run postgres_rotate_credentials --new-password-stdin
```

Execute after reviewing the masked plan:

```bash
printf '%s\n' 'new-password' | uv run postgres_rotate_credentials --new-password-stdin --execute
```

Update the configured password holder first, then rotate the running role.
When standard input is a TTY, omitting the new-password option prompts for it.
`--new-password` remains available for compatibility, but exposes the value in
process arguments. `--allow-config-password` explicitly opts in to using the
configured password as the new value.
`--current-password-stdin` also accepts the current password without placing it
in process arguments; otherwise the configured current password is used.
When more than one stdin option is used, the new password is read first.

If you are replacing the application role rather than only rotating the
password:

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run postgres_rotate_credentials \
  --current-user repom \
  --current-password-stdin \
  --new-user mine_py_app \
  --new-password-stdin \
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
container. The pgAdmin user-management documentation describes password updates
with `--password` and does not document a stdin or environment-variable input
for this value, so the masked repom output does not prevent short-lived
process-argument exposure while the command runs. Dry-run first:

```bash
printf '%s\n' 'new-password' | uv run pgadmin_rotate_password --new-password-stdin
```

Execute after reviewing the masked command:

```bash
printf '%s\n' 'new-password' | uv run pgadmin_rotate_password --new-password-stdin --execute
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
PostgreSQL data volume. It is also the lower exposure path when passing the
new pgAdmin password through `setup.py update-user --password` is not acceptable.

## Notes

- Rotation output masks passwords.
- PostgreSQL execution uses `PGPASSWORD` for the current password instead of
  embedding it in the command line, and sends SQL through stdin so the new
  password is not placed in the `psql` process arguments.
- Review dry-run output before passing `--execute`.
