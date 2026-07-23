# Redis guides

- [Configuration and service lifecycle](redis_manager_guide.md)
- [Credential rotation](credential_rotation.md)
- [Docker responsibility boundary](../features/docker_manager_guide.md)

Use `uv run repom_info` to inspect the effective configuration. The repository
hook applies `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, and `REDIS_DB` to
the connection settings.

```bash
uv run redis_generate
uv run redis_start
uv run redis_stop
uv run redis_remove
```

`REDIS_PORT` is also the published port used by the current Compose generator.
