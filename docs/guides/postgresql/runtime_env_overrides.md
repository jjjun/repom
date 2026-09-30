# PostgreSQL Runtime Env Overrides

PostgreSQL and pgAdmin runtime overrides are provided by helper functions under
`repom.config_hooks/`. Call them at the end of your `CONFIG_HOOK` after setting
project defaults.

```python
from repom.config_hooks.database import apply_database_env_overrides
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides
from repom.config_hooks.postgres import apply_postgres_env_overrides


def hook_config(config):
    config.db_type = "postgres"
    config.db_name = "myapp"

    apply_database_env_overrides(config)
    apply_postgres_env_overrides(config)
    apply_pgadmin_env_overrides(config)
    return config
```

Supported variables:

| Variable | Target |
|---|---|
| `DB_TYPE` | `config.db_type` |
| `REPOM_DATABASE_URL` / `DATABASE_URL` | `config.db_url` (`REPOM_DATABASE_URL` wins) |
| `POSTGRES_USER` | `config.postgres.user` |
| `POSTGRES_PASSWORD` | `config.postgres.password` |
| `POSTGRES_HOST` | `config.postgres.host` |
| `POSTGRES_PORT` | `config.postgres.port` |
| `POSTGRES_HOST_PORT` | `config.postgres.container.host_port` |
| `REPOM_POSTGRES_DB` | `config.postgres.database` |
| `POSTGRES_EXPOSE_TO_LAN` | `config.postgres.container.expose_to_lan` |
| `PGADMIN_DEFAULT_EMAIL` | `config.pgadmin.email` |
| `PGADMIN_DEFAULT_PASSWORD` | `config.pgadmin.password` |
| `PGADMIN_HOST_PORT` | `config.pgadmin.container.host_port` |
| `PGADMIN_EXPOSE_TO_LAN` | `config.pgadmin.container.expose_to_lan` |

`POSTGRES_PORT`, `POSTGRES_HOST_PORT`, and `PGADMIN_HOST_PORT` are validated as
integer ports between 1 and 65535. `REPOM_POSTGRES_DB` pins the PostgreSQL
database name exactly, so repom does not append the usual `exec_env` suffix. It
affects PostgreSQL URL construction when no full database URL override is set.
When `config.db_url` is overridden, `db_type` follows the URL backend instead;
if an explicit `DB_TYPE` disagrees, the URL backend wins and repom logs one
warning for that mismatch. SQLite selection without a URL override still follows
`db_type`, including the default in-memory SQLite URL for `exec_env=test`.

`POSTGRES_EXPOSE_TO_LAN` and `PGADMIN_EXPOSE_TO_LAN` accept a boolean
(`1`/`true`/`yes`/`on` or `0`/`false`/`no`/`off`). `postgres_generate` publishes
the container port on `127.0.0.1` unless the corresponding flag is `true`, in
which case it binds `0.0.0.0` and the service becomes reachable from every
host on the local network.

Use `REPOM_DATABASE_URL` / `DATABASE_URL` only when you want a full URL override
for every environment. Those variables set `config.db_url` directly and bypass
the normal `db_type` URL construction. PostgreSQL overrides still receive the
same TLS policy as generated URLs: if the URL omits `sslmode`, repom uses
`config.postgres.sslmode` when set, or defaults to `prefer` outside prod and for
local or hostless URLs, and `require` for remote prod hosts. A configured
`config.postgres.sslrootcert` is added when repom supplies the missing
`sslmode`, unless the URL already has `sslrootcert`. An explicit URL `sslmode`
is preserved and validated; `disable`, `allow`, and `prefer` raise `ValueError`
for remote prod hosts. Set the URL's `sslmode` to `require` or stronger to fix
that error. Non-PostgreSQL overrides are returned unchanged.

These env variables affect repom's runtime config and generated compose files
when the helpers are called before `postgres_generate` / `postgres_start`.

For existing Docker volumes, changing environment variables alone does not
change initialized PostgreSQL roles or pgAdmin users. Use
[credential_rotation.md](credential_rotation.md) for data-preserving rotation
steps.
