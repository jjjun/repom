# PostgreSQL セットアップガイド

repom は PostgreSQL と任意の pgAdmin を Docker Compose で管理できます。Docker
Desktop または Docker Engine と Compose plugin が必要です。

## インストール

```bash
uv sync --extra postgres
```

リポジトリ自身の開発設定は `.env.example` の
`CONFIG_HOOK=repom.config_hook:hook_config` を使います。この hook は `dev` /
`prod` で PostgreSQL を選び、repom 用の container 設定を適用します。

利用側プロジェクトでは自身の hook で設定してください。

```python
from repom.config_hooks.database import apply_database_env_overrides
from repom.config_hooks.pgadmin import apply_pgadmin_env_overrides
from repom.config_hooks.postgres import apply_postgres_env_overrides


def hook_config(config):
    config.db_type = "postgres"
    config.db_name = "myapp"
    config.postgres.container.host_port = 5432
    config.pgadmin.container.enabled = False

    apply_database_env_overrides(config)
    apply_postgres_env_overrides(config)
    apply_pgadmin_env_overrides(config)
    return config
```

## 環境変数

```dotenv
DB_TYPE=postgres
POSTGRES_USER=repom
POSTGRES_PASSWORD=change-me
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_HOST_PORT=5432
# REPOM_POSTGRES_DB=myapp_dev

# pgAdmin を使う場合
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=change-me
PGADMIN_HOST_PORT=5050
```

`POSTGRES_PORT` はアプリケーションの接続先 port、
`POSTGRES_HOST_PORT` は生成する container の host mapping です。両者を変更する
構成では同じ値に揃えてください。すべての override は
[runtime_env_overrides.md](runtime_env_overrides.md) を参照してください。

秘密値は `.env` または deployment secret に置き、`.env.example` や生成済み資料へ
実 credential を記録しないでください。

## 生成と起動

```bash
uv run postgres_generate
uv run postgres_start
uv run repom_info
```

生成物:

```text
<data_path>/postgres/
├── docker-compose.generated.yml
├── postgresql_init/
│   └── 01_init_databases.sql
└── servers.json                 # pgAdmin 有効時
```

生成物は runtime artifact です。設定の正本は `CONFIG_HOOK` と環境変数です。

## 停止と削除

```bash
uv run postgres_stop
uv run postgres_remove
```

`postgres_remove` は container と volume を削除するため、保存データが不要なことを
確認してから実行してください。

## credential rotation

rotation command は既定で dry-run です。計画を確認してから実行モードへ進みます。
引数と rollback の注意点は [credential rotation](credential_rotation.md) を
参照してください。

```bash
uv run postgres_rotate_credentials --help
uv run pgadmin_rotate_password --help
```

## 外部 PostgreSQL

Docker 管理を使わない場合は `REPOM_DATABASE_URL` を指定できます。この値は
`DATABASE_URL` や個別の PostgreSQL 設定より優先されます。

```dotenv
REPOM_DATABASE_URL=postgresql+psycopg://user:password@db.example:5432/myapp
```

接続先や password を含む URL を log、commit、資料へ残さないでください。

## トラブルシューティング

- 有効設定: `uv run repom_info`
- Docker 状態: `docker ps`
- container log: `docker logs <container-name>`
- port 競合: `POSTGRES_HOST_PORT` と pgAdmin host port を確認
- DB 名: `REPOM_POSTGRES_DB` が指定されていなければ `db_name` と `EXEC_ENV` から生成

関連資料:

- [PostgreSQL ガイド一覧](README.md)
- [Docker manager の責務境界](../features/docker_manager_guide.md)
- [CONFIG_HOOK](../features/config_hook_guide.md)
- [`repom/postgres/manage.py`](../../../repom/postgres/manage.py)
