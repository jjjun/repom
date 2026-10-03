# PostgreSQL の実行時環境変数

環境変数を `CONFIG_HOOK` から反映する方法と hook の設定例は
[CONFIG_HOOK ガイド](../features/config_hook_guide.md)を参照してください。
`apply_repom_env_overrides()` は repom が提供する環境変数 override をまとめて適用し、
各 helper の呼び出し順も定義します。
`repom.config_hooks.parsing` は環境変数の boolean、integer、port 値を解析する共通 helper を
提供します。

## 対応する環境変数

repom の database、PostgreSQL、pgAdmin、SQLite の各 override helper が読む変数は次のとおりです。

| 変数 | 設定先 |
|---|---|
| `DB_TYPE` | `config.db_type` |
| `REPOM_DATABASE_URL` / `DATABASE_URL` | `config.db_url` |
| `SQLALCHEMY_ECHO` | `config.enable_sqlalchemy_echo` |
| `SQLALCHEMY_ECHO_LEVEL` | `config.sqlalchemy_echo_level` |
| `SQLALCHEMY_HIDE_PARAMETERS` | `config.sqlalchemy_hide_parameters` |
| `SQLALCHEMY_POOL_SIZE` | `config.db_pool_size` |
| `SQLALCHEMY_MAX_OVERFLOW` | `config.db_max_overflow` |
| `SQLALCHEMY_POOL_TIMEOUT` | `config.db_pool_timeout` |
| `SQLALCHEMY_POOL_RECYCLE` | `config.db_pool_recycle` |
| `SQLALCHEMY_POOL_PRE_PING` | `config.db_pool_pre_ping` |
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
| `SQLITE_DB_PATH` | `config.sqlite.db_path` |
| `SQLITE_DB_FILE` | `config.sqlite.db_file` |
| `SQLITE_USE_FILE_DB` / `SQLITE_USE_IN_MEMORY_FOR_TESTS` | `config.sqlite.use_in_memory_for_tests` |

`POSTGRES_PORT`、`POSTGRES_HOST_PORT`、`PGADMIN_HOST_PORT` は 1 から 65535 の整数に
限ります。expose 用の変数は `1` / `true` / `yes` / `on` または
`0` / `false` / `no` / `off` を受け付けます。
`REPOM_POSTGRES_DB` は PostgreSQL の DB 名を指定値に固定し、通常の `exec_env` suffix を
追加しません。これは完全な DB URL override がないときに有効です。

## DB URL override と TLS policy

空でない `REPOM_DATABASE_URL` を最優先し、空または未設定なら `DATABASE_URL` を使います。
選ばれた値は `config.db_url` に設定され、`config.db_url_overridden` は `True` になります。
この場合、URL の backend に応じて `db_type` が決まります。明示された `DB_TYPE` と backend が
異なるときは URL が優先され、repom は不一致について warning を1回記録します。
`DB_TYPE` で選ぶ通常の URL 構築を使う場合、`config.db_url_overridden` は `False` です。

PostgreSQL URL で `sslmode` が省略されると、`config.postgres.sslmode` の明示値、
`PGSSLMODE`、または環境と接続先に応じた既定値が使われます。`EXEC_ENV` を正規化した値が
`prod` または `production` alias の場合、リモート接続先には `require` 以上が必要です。
URL に host がない場合も `PGHOST` と `PGHOSTADDR` を接続先判定に使います。`PGSERVICE`
または `service` が選択され、host と hostaddr の両方を明示していない場合は接続先を
解決できないものとして扱い、`require` 以上を要求します。これらの環境設定がなく、service
も選択されていない hostless URL はローカル接続として扱い、既定値は `prefer` です。
それ以外の環境では既定値は `prefer` です。URL override と通常の設定の両方に同じ
URL-level policy が適用されます。

接続先と TLS の検証範囲は entry point ごとに異なります。

| Entry point | URL の設定 | `engine_kwargs.connect_args` |
| --- | --- | --- |
| `RepomConfig.db_url` | URL の host / query と環境 fallback を検証します。 | 対象外です。 |
| `DatabaseManager` / `resolve_engine_settings()` | URL と環境 fallback を含む実効接続先を検証します。 | `host` / `hostaddr` / `service` / `dsn` と TLS を検証し、URL より優先します。 |
| `repom_info` / 同期 `database_info` probe | probe に渡された config を使い、共有 resolver で検証します。 | `DatabaseManager` と同じ検証を行い、短い `connect_timeout` のみ上書きします。 |
| Alembic engine / `AlembicReset` / 同期 test fixture / consumer-built engine | URL-level policy のみ、または検証なしです。 | 共有 resolver を呼ばない限り検証されません。 |
| PostgreSQL client tools | client-tool 固有の URL / host policy を使い、destination query overrides を拒否します。 | SQLAlchemy engine kwargs の対象外です。 `sslmode` / `sslrootcert` query と configured-host の TLS policy を適用し、host 指定を迂回する `PGHOSTADDR` / `PGSERVICE` は child process 環境から除きます。 |

独自の engine を作る場合は、URL-level policy だけでは `connect_args` による接続先変更を検証できません。
実効設定の検証には `DatabaseManager.resolve_engine_settings()` を使ってください。

`config.postgres.sslrootcert` があり、URL で `sslmode` を省略したとき、repom が補う URL に
`sslrootcert` がなくてもその値を追加します。URL で `sslmode` を明示した場合は値を保持したうえで検証します。
正規化後の環境が `prod` で接続先がリモート host のとき、`disable`、`allow`、`prefer` は
`ValueError` になります。`require` または `verify-ca` / `verify-full` を指定してください。
URL と `connect_args` に `sslmode` がなく、`config.postgres.sslmode` も未設定の場合は
`PGSSLMODE` を検証して使います。選択された mode は sync / async 両方の engine に反映されます。
共有 resolver を使う engine では、接続先の判定に URL authority の host に加えて、
URL query、`engine_kwargs.connect_args`、および `PGHOST` / `PGHOSTADDR` の fallback を使います。
`PGHOSTADDR` は URL host が明示されている場合も候補に含め、実際の接続先アドレスとして判定します。
libpq が対応するカンマ区切りの複数 host では、リモート host が一つでも含まれるとリモートとして扱います。
`PGSERVICE`、URL query の `service`、または `connect_args` の `service` が選択されていて
host と hostaddr の両方を明示していない場合は、`pg_service.conf` を解析せず接続先を未解決として扱います。
URL query または
共有 resolver を使う engine entry point では、URL query または `connect_args` の `dsn` は
prod で接続先と TLS 設定を安全に検証できないため使用できません。
asyncpg は `host` を使えますが、
`hostaddr` はサポートしないため共有 resolver を使う engine 設定時に拒否されます。
`host` が Unix socket path または loopback のみの場合はローカルとして扱います。
`DatabaseManager` の engine 作成時の warning は connect args を含む実効接続先と TLS 設定を表示します。

URL override は `db_backup`、`db_restore`、`db_create`、`db_delete`、`db_sync_master` の対象にも
なります。file-based SQLite の場合も override URL の path を使い、in-memory SQLite の backup / restore は
拒否されます。PostgreSQL の backup と restore の詳細は
[バックアップガイド](../features/backup_guide.md)、master data sync が managed container を
skip する条件は[マスターデータ同期ガイド](../features/master_data_sync_guide.md)を参照してください。

URL override がなく SQLite を使う場合、正規化後の `EXEC_ENV=test` かつ
`sqlite.use_in_memory_for_tests=True` なら既定の URL は in-memory SQLite です。
`SQLITE_USE_FILE_DB` と `SQLITE_USE_IN_MEMORY_FOR_TESTS` でこの選択を上書きできます。
SQLite の file path 変数は `SQLITE_DB_PATH` と `SQLITE_DB_FILE` です。

`POSTGRES_EXPOSE_TO_LAN` と `PGADMIN_EXPOSE_TO_LAN` が `true` の場合、生成した container port は
`0.0.0.0` に bind されます。既定では `127.0.0.1` のみへ公開されます。

実行時設定を確認するには `uv run repom_info` を使ってください。既存 Docker volume の
PostgreSQL role や pgAdmin user は環境変数を変更しただけでは変わりません。
データを保った認証情報の変更は[認証情報ローテーション](credential_rotation.md)を参照してください。
