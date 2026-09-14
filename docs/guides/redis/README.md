# Redis guides

- [Configuration and service lifecycle](redis_manager_guide.md)
- [Credential rotation](credential_rotation.md)
- [Docker responsibility boundary](../features/docker_manager_guide.md)

Use `uv run repom_info` to inspect the effective configuration. The repository
hook applies `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`, and
`REDIS_EXPOSE_TO_LAN` to the connection settings.

```bash
uv run redis_generate
uv run redis_start
uv run redis_stop
uv run redis_remove
```

`REDIS_PORT` is also the published port used by the current Compose generator.
The generated port is published on `127.0.0.1` by default; set
`REDIS_EXPOSE_TO_LAN=true` to bind `0.0.0.0` instead, for a project that
genuinely needs LAN access. When a password is configured, `redis_generate`
writes it to a `.env` file (mode 0600) next to the compose file instead of
inlining it in `docker-compose.generated.yml`.
