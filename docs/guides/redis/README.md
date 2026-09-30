# Redis guides

- [Configuration and service lifecycle](redis_manager_guide.md)
- [Credential rotation](credential_rotation.md)
- [Docker responsibility boundary](../features/docker_manager_guide.md)

Use `uv run repom_info` to inspect the effective configuration. The repository
hook applies `REDIS_HOST`, `REDIS_PORT`, `REDIS_HOST_PORT`, `REDIS_PASSWORD`,
`REDIS_DB`, and `REDIS_EXPOSE_TO_LAN` to the Redis settings.

```bash
uv run redis_generate
uv run redis_start
uv run redis_stop
uv run redis_remove
```

`REDIS_HOST_PORT` sets the published host port. If it is unset, the generator
publishes `REDIS_PORT`, preserving the existing default. The generated port is
bound to `127.0.0.1` by default; set `REDIS_EXPOSE_TO_LAN=true` to bind
`0.0.0.0` instead, for a project that genuinely needs LAN access.
`REDIS_PASSWORD` is required by `redis_generate`, which writes it to a `.env`
file (mode 0600) next to the compose file instead of inlining it in
`docker-compose.generated.yml`.

## Client connection settings

`RedisConfig.connection_kwargs()` returns the host, connection port, database,
and optional password as redis-py keyword arguments. Use `url()` to build a
Redis URL without credentials by default, or pass `include_password=True` when
a client needs a password-bearing URL. Passwords in URLs are percent-encoded;
use `safe_url()` for logging because it masks any configured password.

```python
from repom.config import RepomConfig

redis_config = RepomConfig().redis
connection_kwargs = redis_config.connection_kwargs()
safe_url = redis_config.safe_url()
```
