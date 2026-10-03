# Docker manager と Compose の責務境界

汎用の `DockerManager` と `DockerCommandExecutor` は
`basekit.docker_manager` が正本です。汎用の Compose 定義
(`DockerComposeGenerator`、`DockerService`、`DockerVolume`) とその API は
`basekit.docker_compose` が正本です。repom は次のサービス固有 manager と共有 lifecycle
wrapper、PostgreSQL / Redis 向けの Compose 設定生成だけを所有します。

- `repom.postgres.manage.PostgresManager`
- `repom.redis.manage.RedisManager`
- `repom.docker_service.ensure_running()`

## 利用者向け API

通常は Python クラスを直接生成せず、console script を使用します。

| PostgreSQL | Redis |
| --- | --- |
| `uv run postgres_generate` | `uv run redis_generate` |
| `uv run postgres_start` | `uv run redis_start` |
| `uv run postgres_stop` | `uv run redis_stop` |
| `uv run postgres_remove` | `uv run redis_remove` |

`ensure_running()` は service が停止しているとき、現在の設定から秘密情報を含まない
生成物を書き直してから起動します。既存の `.env` はそのまま再利用し、存在しない場合は
通常の生成処理で作成します。設定した実 credential が保存済み `.env` と異なる場合や、
必要な key が `.env` にない場合は起動を拒否します。credential の変更には対応する
rotation command を使ってください。明示的な `*_generate` と `*_start` は従来どおり
生成物を再生成し、現在の credential と異なる `.env` の上書きは拒否します。秘密情報を
意図的に置き換える場合は `--force-regenerate` を指定してください。内容が変わる場合は
前の `.env` を mode `0600` の `.env.bak` として保存します。

複数の `EXEC_ENV` が同じ `data_path` を共有する場合、各環境の auto-start はその環境の
container 名、port、volume を使って秘密情報を含まない生成物を書き直します。一方、
compose directory の `.env` は共有されるため、同じ service を使う環境は同一の secret を
設定してください。異なる実 credential が設定されていると `ensure_running()` は拒否します。
`*_stop` と `*_remove` も現在の設定で Compose file を書き直してから実行するため、対象環境の
`EXEC_ENV` を指定してください。

`postgres_remove` と `redis_remove` は Compose の `down -v` を実行し、named volume も削除します。
確認プロンプトや production 環境の拒否はないため、実行前に `EXEC_ENV` と対象 volume を確認してください。
`postgres_rotate_credentials`、`redis_rotate_password`、`pgadmin_rotate_password` は既定で dry-run です。
実際に credential を変更するには `--execute` が必要です。明示的な password option は process argument に
値を含むため、stdin option または TTY prompt を使用してください。pgAdmin volume の再作成には
`--recreate-volume`、`--execute`、`--confirm-recreate-volume` のすべてが必要です。

通常の `*_generate` は有効な service の credential が未設定または placeholder の場合に失敗します。
auto-start は既存 `.env` の必須 key と設定値との差を確認しますが、設定側が空または placeholder の場合に
`.env` 内の空値・placeholder 値を独立して拒否しません。`*_stop` と `*_remove` は credential 検証なしで
生成物を書き直すため、既存 `.env` の値は検証しません。

アプリ起動時に必要なサービスを保証する場合は、サービス固有の
`ensure_running()` を利用できます。

```python
from repom.postgres.manage import ensure_running as ensure_postgres_running
from repom.redis.manage import ensure_running as ensure_redis_running

ensure_postgres_running(timeout_seconds=30, include_pgadmin=True)
ensure_redis_running(timeout_seconds=30)
```

Docker CLI がない場合、起動失敗、readiness timeout は `RuntimeError` として
呼び出し側へ伝播します。アプリケーションは lifecycle 境界で処理してください。

Docker Compose v2 plugin (`docker compose`) が使える場合は v2 を優先し、使えない場合は
standalone `docker-compose` に fallback します。v1 で作成した stack を v2 の
`up -d` で初めて起動すると container が一度再作成されることがありますが、named volume は
保持されます。

## Compose 生成時の安全チェック

`repom/docker_compose_safety.py` は Compose に渡す YAML 文字列を quote し、値に改行・復帰・
NUL 文字があれば拒否します。port は既定で `127.0.0.1` に bind し、秘密情報を含む
`.env` file は POSIX では mode `0600` の一時ファイルを内容の書き込み前に排他的に作成し、完成後に原子的に置き換えます。repom は Windows ACL を設定せず、compose directory 自体も制限しません。

`repom.postgres.manage.generate()` と `repom.redis.manage.generate()` は、password が
未設定または `CHANGE_ME` のままの場合や、password に改行・復帰・NUL 文字が含まれる
場合に `ValueError` を送出します。`repom.docker_service.DockerUnavailableError` は
`RuntimeError` の subclass で、Docker CLI がない場合や daemon に接続できない場合に
送出されます。`repom.docker_service.is_container_running(container_name)` は container
の稼働状態を exact name match で `bool` として返し、Docker が利用できない場合は
`DockerUnavailableError` を送出します。

生成時には image reference、container name、named-volume name を検証します。`data_path` などから
作る host bind-mount path は検証しません。Redis の health check は `redis-cli ping` を使い、password は
Compose service environment の `REDISCLI_AUTH` で渡します。Docker の service environment は
`docker inspect` から参照できます。

関連資料:

- [PostgreSQL ガイド](../postgresql/README.md)
- [Redis ガイド](../redis/README.md)
- [`repom/docker_service.py`](../../../repom/docker_service.py)
- [`repom/postgres/manage.py`](../../../repom/postgres/manage.py)
- [`repom/redis/manage.py`](../../../repom/redis/manage.py)
- [技術資料の所有範囲](../../technical/README.md#所有範囲と履歴)
