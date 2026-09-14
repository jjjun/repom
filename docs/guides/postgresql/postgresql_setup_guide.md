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
# POSTGRES_EXPOSE_TO_LAN=true

# pgAdmin を使う場合
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=change-me
PGADMIN_HOST_PORT=5050
# PGADMIN_EXPOSE_TO_LAN=true
```

`POSTGRES_EXPOSE_TO_LAN` / `PGADMIN_EXPOSE_TO_LAN` は既定で無効です。無効な間は
生成した container の port を `127.0.0.1` にのみ公開し、有効にすると
`0.0.0.0` へ公開して LAN 上の他ホストからも到達可能になります。LAN 公開が
本当に必要なプロジェクトでのみ有効にしてください。

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
├── .env                          # POSTGRES_PASSWORD 等、生成した secrets（0600）
├── postgresql_init/
│   └── 01_init_databases.sql
└── servers.json                 # pgAdmin 有効時
```

`docker-compose.generated.yml` は `POSTGRES_PASSWORD` / `PGADMIN_DEFAULT_PASSWORD`
の実値を含みません。これらは同じディレクトリの `.env` に書き出され、compose
は `${POSTGRES_PASSWORD}` のような変数参照でこれを読み込みます。生成物は
runtime artifact です。設定の正本は `CONFIG_HOOK` と環境変数です。

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

`config.postgres` 経由で `db_url` を組み立てる場合、sslmode は
`config.postgres.sslmode`（未設定時は exec_env 別の既定値: dev/test は
`prefer`、prod は `require`）から補われます。`config.postgres.sslrootcert`
を設定すると `sslrootcert` クエリパラメータも付与され、`verify-full` の検証に
使えます。`EXEC_ENV=prod` でリモートホストへ接続する場合、`require` 未満の
sslmode は `db_url` アクセス時に `ValueError` になります。

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
