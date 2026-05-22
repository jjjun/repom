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
| `PGADMIN_DEFAULT_EMAIL` | `config.pgadmin.email` |
| `PGADMIN_DEFAULT_PASSWORD` | `config.pgadmin.password` |

`POSTGRES_PORT` is validated as an integer port between 1 and 65535. These env
variables affect repom's runtime config and generated compose files when the
helpers are called before `postgres_generate` / `postgres_start`.
