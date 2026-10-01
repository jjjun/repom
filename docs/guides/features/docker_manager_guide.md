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

`ensure_running()` は Compose file と `.env` が両方存在する場合、それらを再利用します。
どちらかがない場合だけファイルを生成します。明示的な `*_generate` と `*_start` は
ファイルを再生成しますが、現在の credential と異なる `.env` の上書きは拒否します。
既存 service の credential を変更するには対応する rotation command を使うか、
秘密情報を意図的に置き換える場合に `--force-regenerate` を指定してください。
内容が変わる場合は前の `.env` を mode `0600` の `.env.bak` として保存します。

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
`.env` file は mode `0600` で作成します。

`repom.postgres.manage.generate()` と `repom.redis.manage.generate()` は、password が
未設定または `CHANGE_ME` のままの場合や、password に改行・復帰・NUL 文字が含まれる
場合に `ValueError` を送出します。`repom.docker_service.DockerUnavailableError` は
`RuntimeError` の subclass で、Docker CLI がない場合や daemon に接続できない場合に
送出されます。`repom.docker_service.is_container_running(container_name)` は container
の稼働状態を `bool` で返し、Docker が利用できない場合は `DockerUnavailableError` を
送出します。

関連資料:

- [PostgreSQL ガイド](../postgresql/README.md)
- [Redis ガイド](../redis/README.md)
- [`repom/docker_service.py`](../../../repom/docker_service.py)
- [`repom/postgres/manage.py`](../../../repom/postgres/manage.py)
- [`repom/redis/manage.py`](../../../repom/redis/manage.py)
- [技術資料の所有範囲](../../technical/README.md#所有範囲と履歴)
