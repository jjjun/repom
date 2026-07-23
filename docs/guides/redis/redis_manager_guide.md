# Redis Manager ガイド

repom は Redis の設定、Compose 生成、起動・停止、password rotation を提供します。
Python client を利用する場合は optional dependency を追加します。

```bash
uv sync --extra redis
```

## 設定

```dotenv
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

`REDIS_PORT` は接続先と生成 Compose の公開 port です。利用側 hook では、
プロジェクト既定値の後に environment override を適用します。

```python
from repom.config_hooks.redis import apply_redis_env_overrides


def hook_config(config):
    config.redis.port = 6379
    config.redis.container.container_name = "myapp_redis"
    apply_redis_env_overrides(config)
    return config
```

## 生成と起動

```bash
uv run redis_generate
uv run redis_start
uv run repom_info
```

生成物:

```text
<data_path>/redis/
├── docker-compose.generated.yml
└── redis_init/
    └── redis.conf
```

設定の正本は `CONFIG_HOOK` と環境変数です。生成物を手編集しても、次の
`redis_generate` で上書きされます。

## 停止と削除

```bash
uv run redis_stop
uv run redis_remove
```

`redis_remove` は container と volume を削除するため、保存データが不要なことを
確認してから実行してください。

## アプリ起動時の確認

アプリ lifecycle で Redis が必要な場合は、サービス固有 helper を使えます。

```python
from repom.redis.manage import ensure_running

ensure_running(timeout_seconds=30)
```

Docker CLI がない場合や readiness timeout は `RuntimeError` になります。

## password rotation

```bash
uv run redis_rotate_password --help
```

rotation は接続中 client への影響を伴います。dry-run、環境変数更新、client の
再接続手順は [credential rotation](credential_rotation.md) を参照してください。

## トラブルシューティング

- 有効設定: `uv run repom_info`
- Docker 状態: `docker ps`
- container log: `docker logs <container-name>`
- 接続確認: `redis-cli -h <host> -p <port> ping`
- password 利用時: `REDISCLI_AUTH` など、shell history に秘密値を残しにくい方法を使う

関連資料:

- [Redis ガイド一覧](README.md)
- [Docker manager の責務境界](../features/docker_manager_guide.md)
- [`repom/redis/manage.py`](../../../repom/redis/manage.py)
