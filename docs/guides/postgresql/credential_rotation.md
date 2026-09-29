# PostgreSQL And pgAdmin Credential Rotation

repom can generate compose files with new PostgreSQL and pgAdmin credentials,
but existing Docker volumes keep the credentials that were initialized earlier.
Use the rotation helpers when you need to harden an existing local or
self-managed environment without deleting PostgreSQL data.

## PostgreSQL

Dry-run the SQL plan first:

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run postgres_rotate_credentials \
  --new-password-stdin \
  --current-password-stdin
```

Execute after reviewing the masked plan:

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run postgres_rotate_credentials \
  --new-password-stdin \
  --current-password-stdin \
  --execute
```

Update the configured password holder to the new password before rotating the
running role. The PostgreSQL role still has its old password at that point, so
pass that old value with `--current-password-stdin`, as above. If the configured
password holder still contains the role's old password, that configured value is
used as the current password when no current-password option is supplied.
`--current-password` and `--new-password` expose their values in process
arguments. Prefer the corresponding `*-stdin` options; when both are used, the
new password is read from stdin first. When stdin is a TTY, omitting the
new-password option prompts for the new password. `--allow-config-password`
explicitly opts in to using the configured password as the new value.

`--database` can be repeated to select databases; by default the command targets
`db_name`, `db_name_dev`, and `db_name_test`. `--schema` can be repeated to
select schemas and defaults to `public`.

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

repom invokes this command with `/venv/bin/python` and `/pgadmin4/setup.py`,
paths hard-coded for the pgAdmin image. If that update command is not usable for
the installed image, set the new `PGADMIN_DEFAULT_EMAIL` and
`PGADMIN_DEFAULT_PASSWORD` values, then recreate only the pgAdmin volume. Review
the dry-run before executing the removal:

```bash
uv run pgadmin_rotate_password --recreate-volume
uv run pgadmin_rotate_password --recreate-volume --execute --confirm-recreate-volume
uv run postgres_start
```

`postgres_start` regenerates compose using the current configuration before
starting the containers. This fallback removes pgAdmin's own saved UI state,
but it does not remove the PostgreSQL data volume. It is also the lower exposure
path when passing the new pgAdmin password through `setup.py update-user
--password` is not acceptable.

## Notes

- Rotation output masks passwords.
- PostgreSQL execution passes `PGPASSWORD` for the current password to the
  container with `docker exec --env-file`, not the command line or the host
  process environment: the value is written to a 0600 temporary file that is
  removed as soon as the rotation finishes. SQL is sent through stdin so the
  new password is not placed in the `psql` process arguments either.
- A failed rotation, including the pgAdmin `update-user` argv exposure noted
  above, raises an error with the password masked instead of a raw subprocess
  traceback.
- Review dry-run output before passing `--execute`.
