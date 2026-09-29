# Docker Compose 基盤の責務境界

汎用の Compose 定義 (`DockerComposeGenerator`, `DockerService`,
`DockerVolume`) は `basekit.docker_compose` が正本です。repom はこの API を
PostgreSQL と Redis の構成生成に利用しますが、汎用 API 仕様はここへ複製しません。

起動時は Docker Compose v2 plugin (`docker compose`) が使える場合に優先され、使えない
場合は standalone `docker-compose` に fallback します。v1 で作成した stack を初めて
v2 の `up -d` で起動すると container が一度再作成される場合がありますが、named
volume は保持されます。

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

## repom の安全チェック

repom は `repom/docker_compose_safety.py` で、Compose に渡す YAML 文字列を quote し、
値に改行・復帰・NUL 文字があれば拒否します。port は既定で `127.0.0.1` に bind し、
秘密情報を含む `.env` file は mode `0600` で作成します。

- [PostgreSQL ガイド](../postgresql/README.md)
- [Redis ガイド](../redis/README.md)
- [Docker manager の責務境界](docker_manager_guide.md)
- [PostgreSQL 実装](../../../repom/postgres/manage.py)
- [Redis 実装](../../../repom/redis/manage.py)
