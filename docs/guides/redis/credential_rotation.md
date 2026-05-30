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
uv run redis_rotate_password --new-password "new-password" --old-password "old-password"
```

Execute it:

```bash
uv run redis_rotate_password \
  --new-password "new-password" \
  --old-password "old-password" \
  --execute
```

If Redis currently has no password, omit `--old-password`.

After execution, repom regenerates `redis.conf` with the new password so the
setting survives restart. The runtime command passes the old password through
`REDISCLI_AUTH` and sends the new password through stdin.

## Notes

- If no Redis password is configured, generated Redis behavior remains
  unauthenticated.
- Rotation output masks passwords.
- `CONFIG SET requirepass` affects the running Redis instance immediately.
