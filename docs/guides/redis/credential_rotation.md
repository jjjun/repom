# Redis Credential Rotation

`REDIS_PASSWORD` is applied to repom's Redis config when
`repom.config_hooks.redis.apply_redis_env_overrides()` is called. Generated
Redis instances pass that value to the container via the service environment
and start Redis with `--requirepass`; the generated `redis.conf` never
contains it. Health checks authenticate with the configured password.

## Fresh Or Regenerated Config

For a fresh data volume, set the password and generate the Redis files:

```bash
REDIS_PASSWORD="new-password" uv run redis_generate
```

Start Redis:

```bash
REDIS_PASSWORD="new-password" uv run redis_start
```

For an existing volume, use `redis_rotate_password` to change its live
password. `redis_generate` and `redis_start` refuse to replace a generated
`.env` when its password differs from the active configuration. Pass
`--force-regenerate` only when intentionally replacing the generated secret;
changed content keeps the previous `.env` as `.env.bak` with mode `0600`.

Connect with:

```bash
REDISCLI_AUTH="new-password" redis-cli -p 6379
```

## Existing Running Instance

`main_rotate_password(argv)` accepts an explicit argument list. A task runner
that parses its own options can call `rotate_redis_password_cli(...)` with
keyword arguments to use the same password prompts, stdin handling, and
execute safeguards as the console command.

Dry-run the runtime password change:

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run redis_rotate_password \
  --new-password-stdin \
  --old-password-stdin
```

Execute it:

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run redis_rotate_password \
  --new-password-stdin \
  --old-password-stdin \
  --execute
```

Update the configured password holder first, then rotate Redis. When standard
input is a TTY, omitting the new-password option prompts for it, and omitting
the old-password option prompts for the current password.
`--new-password` and `--old-password` remain available for compatibility, but
expose their values in process arguments. `--allow-config-password` explicitly
opts in to using the configured password as the new value.
When more than one stdin option is used, the new password is read first.

After execution, repom regenerates the compose files and the `.env` secrets
file with the new password only after Redis confirms the change. This update
uses the explicit secret overwrite path and keeps the previous `.env` as
`.env.bak` when its content changes.
The library function `repom.redis.manage.rotate_password` performs this
compose-dir `.env` update itself, so callers and downstream wrappers do not
need an additional persistence step.
The runtime command passes the old password through `REDISCLI_AUTH` when it is
supplied with `--old-password` or `--old-password-stdin`, or entered at the TTY
prompt, and sends the new password through stdin. `REDISCLI_AUTH` is written to
a 0600 temporary file and passed to the container with `docker exec --env-file`,
and the file is removed as soon as the command finishes, so the old password is
not placed in process arguments. The readiness poll used while starting Redis
never sends a password at all: it pings unauthenticated and treats a NOAUTH
reply as confirmation that the server is up.

## Notes

- Generated Redis always requires a password: `redis_generate` refuses to
  run when `REDIS_PASSWORD` is unset or still `CHANGE_ME`.
- Rotation output masks passwords.
- A failed rotation raises an error with the password masked instead of a raw
  subprocess traceback.
- `CONFIG SET requirepass` affects the running Redis instance immediately.
