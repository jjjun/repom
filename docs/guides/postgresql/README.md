# PostgreSQL guides

- [Setup and service lifecycle](postgresql_setup_guide.md)
- [Runtime environment overrides](runtime_env_overrides.md)
- [Credential rotation](credential_rotation.md)

The effective values depend on the active `CONFIG_HOOK`, `EXEC_ENV`, and
environment overrides. Use `uv run repom_info` before operating on a database;
do not rely on a port, database name, or credential copied from an old example.

Service commands are defined in `pyproject.toml`:

```bash
uv run postgres_generate
uv run postgres_start
uv run postgres_stop
uv run postgres_remove
```
