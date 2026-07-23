# Docker manager の責務境界

汎用の `DockerManager` と `DockerCommandExecutor` は
`basekit.docker_manager` が正本です。repom は次のサービス固有 manager と
共有 lifecycle wrapper だけを所有します。

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

関連資料:

- [PostgreSQL ガイド](../postgresql/README.md)
- [Redis ガイド](../redis/README.md)
- [Compose 基盤の責務境界](docker_compose_guide.md)
- [`repom/docker_service.py`](../../../repom/docker_service.py)
- [Docker manager 移管の履歴](../../technical/docker_manager_code_reduction_analysis.md)
