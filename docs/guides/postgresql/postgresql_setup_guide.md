# PostgreSQL セットアップガイド

repom は PostgreSQL と任意の pgAdmin を Docker Compose で管理できます。Docker
Desktop または Docker Engine と Docker Compose v2 plugin (`docker compose`) または standalone
`docker-compose` が必要です。

両方がある場合は Docker Compose v2 plugin を優先します。v1 で作成した stack を
初めて v2 の `up -d` で起動すると、container が一度再作成される場合がありますが、
named volume は保持されます。

## インストール

```bash
uv sync --extra postgres
```

リポジトリ自身の開発設定は `.env.example` の
`CONFIG_HOOK=repom.config_hook:hook_config` を使います。この hook は正規化した
`EXEC_ENV` が `test` の場合だけ SQLite を選び、それ以外では PostgreSQL を選択します。

利用側プロジェクトの hook 作成方法は[CONFIG_HOOK ガイド](../features/config_hook_guide.md)を
参照してください。

## 環境変数

```dotenv
DB_TYPE=postgres
POSTGRES_USER=repom
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_HOST_PORT=5432
# REPOM_POSTGRES_DB=myapp_dev
# POSTGRES_EXPOSE_TO_LAN=true

# pgAdmin を使う場合
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=CHANGE_ME
PGADMIN_HOST_PORT=5050
# PGADMIN_EXPOSE_TO_LAN=true
```

`POSTGRES_EXPOSE_TO_LAN` / `PGADMIN_EXPOSE_TO_LAN` は既定で無効です。無効な間は
生成した container の port を `127.0.0.1` にのみ公開し、有効にすると
`0.0.0.0` へ公開して LAN 上の他ホストからも到達可能になります。LAN 公開が
本当に必要なプロジェクトでのみ有効にしてください。

container の再起動方針は environment variable ではなく consumer の config hook で設定します。既定値は
`unless-stopped` です。値には `no`、`always`、`unless-stopped`、`on-failure`、または
`on-failure:<正の整数>` を指定できます。以前と同じ挙動にする場合は
`config.postgres.container.restart_policy = "no"`、または pgAdmin に対して
`config.pgadmin.container.restart_policy = "no"` を設定してください。`postgres_stop` は Compose の
`stop` を使うため、明示的に停止した container は次の `postgres_start` まで停止状態を保ちます。

`POSTGRES_PORT` はアプリケーションの接続先 port、
`POSTGRES_HOST_PORT` は生成する container の host mapping です。両者を変更する
構成では同じ値に揃えてください。すべての override は
[runtime_env_overrides.md](runtime_env_overrides.md) を参照してください。

秘密値は `.env` または deployment secret に置き、`.env.example` や生成済み資料へ
実 credential を記録しないでください。`POSTGRES_PASSWORD` / `PGADMIN_DEFAULT_PASSWORD`
が未設定、または `CHANGE_ME` のままだと `postgres_generate` はエラーで停止します。

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

application の `ensure_running()` は停止した PostgreSQL / pgAdmin を起動する前に、現在の
設定から秘密情報を含まない生成物を書き直し、既存の `.env` をそのまま再利用します。
`.env` がない場合は通常の生成処理で作成します。複数の `EXEC_ENV` が同じ `data_path` を
共有すると `.env` も共有されるため、各環境で同じ PostgreSQL / pgAdmin secret を設定して
ください。異なる実 credential や必要な key の不足がある場合は起動を拒否します。
`postgres_stop` と `postgres_remove` も現在の設定で Compose file を書き直すため、対象環境の
`EXEC_ENV` を指定してください。詳細は
[Docker manager ガイド](../features/docker_manager_guide.md)を参照してください。

## 停止と削除

```bash
uv run postgres_stop
uv run postgres_remove
```

`postgres_remove` は container と volume を削除するため、保存データが不要なことを
確認してから実行してください。

## 認証情報のローテーション

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

PostgreSQL URL の TLS 既定値と `sslrootcert`、正規化後の production 判定については
[実行時環境変数ガイドの DB URL と TLS の節](runtime_env_overrides.md#db-url-override-と-tls-policy)を
参照してください。

非同期 PostgreSQL 接続では URL query の `sslmode` / `sslrootcert` を初期値として使い、
`engine_kwargs.connect_args` に同じ設定があればそちらを優先します。URL と
`connect_args` の `connect_timeout` は asyncpg の `timeout` に、
`application_name` は `server_settings.application_name` に変換されます。
`connect_args.timeout` と `connect_args.server_settings.application_name` が URL の値と
重なる場合も、`connect_args` 側の値を使います。`connect_args` 内の
`connect_timeout` と `timeout`、または `application_name` と
`server_settings.application_name` が異なる値なら `ValueError` になります。

asyncpg 固有の接続オプションと既存の `server_settings` は保持されます。
`sslcert`、`sslkey`、`sslpassword`、`sslcrl`、`ssl_min_protocol_version`、
`ssl_max_protocol_version` は asyncpg の DSN option として渡されます。SQLAlchemy の
`prepared_statement_cache_size` などの dialect option は URL に残ります。未対応の URL
option や connect_args は、非同期 engine の設定時に `ValueError` になります。

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
