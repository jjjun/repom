# Redis Credential Rotation

`REDIS_PASSWORD` is applied to repom's Redis config when
`repom.config_hooks.redis.apply_redis_env_overrides()` is called. Generated
Redis instances now persist that value in `redis.conf` with `requirepass`, and
health checks authenticate when a password is configured.

## Fresh Or Regenerated Config

Set the password and regenerate the Redis files:

```bash
REDIS_PASSWORD="new-password" uv run redis_generate
```

Start Redis:

```bash
REDIS_PASSWORD="new-password" uv run redis_start
```

When a password is configured, connect with:

```bash
REDISCLI_AUTH="new-password" redis-cli -p 6379
```

## Existing Running Instance

Dry-run the runtime password change:

```bash
printf '%s\n' 'new-password' | uv run redis_rotate_password --new-password-stdin
```

Execute it:

```bash
printf '%s\n' 'new-password' | uv run redis_rotate_password \
  --new-password-stdin \
  --execute
```

Update the configured password holder first, then rotate Redis. When standard
input is a TTY, omitting the new-password option prompts for it.
`--new-password` and `--old-password` remain available for compatibility, but
expose their values in process arguments. `--allow-config-password` explicitly
opts in to using the configured password as the new value.
When more than one stdin option is used, the new password is read first.

If Redis already has a password, pass it explicitly:

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run redis_rotate_password \
  --new-password-stdin \
  --old-password-stdin \
  --execute
```

After execution, repom regenerates `redis.conf` with the new password so the
setting survives restart. The runtime command passes the old password through
`REDISCLI_AUTH` only when `--old-password` is supplied, and sends the new
password through stdin. `REDISCLI_AUTH` is passed through `docker exec -e`, so
the old password can still be visible through host process inspection while the
command runs.

## Notes

- If no Redis password is configured, generated Redis behavior remains
  unauthenticated.
- Rotation output masks passwords.
- `CONFIG SET requirepass` affects the running Redis instance immediately.
