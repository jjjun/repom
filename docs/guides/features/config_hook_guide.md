# CONFIG_HOOK ガイド

`CONFIG_HOOK` は、repom が作成した `RepomConfig` を利用側プロジェクトの関数へ渡し、
返された設定を有効にする仕組みです。loader の正本は
`basekit.config_hook`、repom 固有の設定項目は `repom.config.RepomConfig` です。

## 最小構成

```python
# myapp/config.py
def hook_config(config):
    config.db_name = "myapp"
    config.model_locations = ["myapp.models"]
    config.allowed_package_prefixes = {"myapp.", "repom."}
    return config
```

```dotenv
CONFIG_HOOK=myapp.config:hook_config
```

hook は必ず1個の config 引数を受け取り、設定オブジェクトを返します。module を
import した時点で新しい `RepomConfig` を作ったり、引数なし関数を登録したりしないで
ください。

## runtime environment override

project の既定値を先に設定し、環境変数 helper を最後に呼びます。

```python
from repom.config_hooks.database import apply_database_env_overrides
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides
from repom.config_hooks.postgres import apply_postgres_env_overrides
from repom.config_hooks.redis import apply_redis_env_overrides
from repom.config_hooks.sqlite import apply_sqlite_env_overrides


def hook_config(config):
    config.db_name = "myapp"
    config.db_type = "postgres"
    config.postgres.container.host_port = 5432

    apply_database_env_overrides(config)
    apply_postgres_env_overrides(config)
    apply_pgadmin_env_overrides(config)
    apply_redis_env_overrides(config)
    apply_sqlite_env_overrides(config)
    return config
```

これにより、コード上の既定値を deployment 環境で上書きできます。サポートする DB
関連変数は [PostgreSQL runtime overrides](../postgresql/runtime_env_overrides.md) と
各 helper の docstring を参照してください。

## 主な設定

| 分類 | 設定例 |
| --- | --- |
| DB | `db_type`, `db_name`, `db_url`, pool 設定 |
| SQLite | `sqlite.db_path`, `sqlite.db_file`, `sqlite.use_in_memory_for_tests` |
| PostgreSQL | `postgres.*`, `postgres.container.*` |
| pgAdmin | `pgadmin.*`, `pgadmin.container.*` |
| Redis | `redis.*`, `redis.container.*` |
| model import | `model_locations`, `allowed_package_prefixes`, `model_excluded_dirs`, `model_import_strict` |
| logging | `log_path`, `enable_sqlalchemy_echo`, `sqlalchemy_echo_level` |

有効値は次で確認します。

```bash
uv run repom_info
```

## 読み込み失敗

module が import できない、属性がない、対象が callable でない場合、
`basekit.config_hook.ConfigHookLoadError` を送出して起動を停止します。設定ミスを
warning だけで無視しません。

確認項目:

1. `CONFIG_HOOK` が `module:callable` 形式か。
2. 利用側 package が Python path にあるか。
3. hook が config 引数を受け取るか。
4. hook が config を返しているか。
5. repom import より前に環境変数が設定されているか。

## repom 自身の hook

`.env.example` の `repom.config_hook:hook_config` は、この repository の開発用です。
`test` では SQLite、`dev` / `prod` では PostgreSQL を選び、repom の model と
container 既定値を設定します。利用側 project はこの hook をそのまま複製せず、自身の
要件に必要な差分だけ定義してください。

関連資料:

- [`repom/config.py`](../../../repom/config.py)
- [`repom/config_hook.py`](../../../repom/config_hook.py)
- [モデル自動 import](auto_import_models_guide.md)
- [README の設定概要](../../../README.md#設定)
