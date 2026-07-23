# Docker Compose 基盤の責務境界

汎用の Compose 定義 (`DockerComposeGenerator`, `DockerService`,
`DockerVolume`) は `basekit.docker_compose` が正本です。repom はこの API を
PostgreSQL と Redis の構成生成に利用しますが、汎用 API 仕様はここへ複製しません。

repom で利用者が操作する入口は console script です。

```bash
uv run postgres_generate
uv run postgres_start
uv run postgres_stop
uv run postgres_remove

uv run redis_generate
uv run redis_start
uv run redis_stop
uv run redis_remove
```

生成先、container 名、port、credential の設定は各サービスガイドを参照してください。

- [PostgreSQL ガイド](../postgresql/README.md)
- [Redis ガイド](../redis/README.md)
- [Docker manager の責務境界](docker_manager_guide.md)
- [PostgreSQL 実装](../../../repom/postgres/manage.py)
- [Redis 実装](../../../repom/redis/manage.py)
