# Redis 管理ガイド

repom は Redis の設定、Compose 生成、起動・停止、password rotation を提供します。
Python client を利用する場合は optional dependency を追加します。

Docker Compose v2 plugin (`docker compose`) と standalone `docker-compose` のどちらも
利用できます。両方がある場合は plugin を優先します。v1 で作成した stack を初めて
v2 の `up -d` で起動すると、container が一度再作成される場合がありますが、named
volume は保持されます。

```bash
uv sync --extra redis
```

## 設定

```dotenv
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
# REDIS_HOST_PORT=6390
REDIS_PASSWORD=CHANGE_ME
REDIS_DB=0
# REDIS_EXPOSE_TO_LAN=true
# REDIS_ALLOW_INSECURE_REMOTE=false
```

`REDIS_PASSWORD` が未設定、または `CHANGE_ME` のままだと `redis_generate` は
エラーで停止します。

`REDIS_PORT` は接続先と生成 Compose の公開 port です。利用側 hook では、
プロジェクト既定値の後に environment override を適用します。
`REDIS_HOST_PORT` を指定した場合は公開 host port にその値を使い、未指定の場合は
`REDIS_PORT` を公開 host port の fallback として使います。`CHANGE_ME` は未設定と同じ
placeholder のため、実際に Redis を生成する前に `REDIS_PASSWORD` を実値に変更してください。

```python
from repom.config_hooks.redis import apply_redis_env_overrides


def hook_config(config):
    config.redis.port = 6379
    config.redis.container.container_name = "myapp_redis"
    apply_redis_env_overrides(config)
    return config
```

### クライアント接続設定

`RedisConfig.connection_kwargs()` は host、接続 port、DB 番号、任意の password を redis-py の
keyword 引数として返します。`url()` は既定で credential を含まない Redis URL を生成します。
password を含める場合は `include_password=True` を指定します。URL 内の password は percent-encode
されます。log には password を mask する `safe_url()` を使ってください。

```python
from repom.config import RepomConfig

redis_config = RepomConfig().redis
connection_kwargs = redis_config.connection_kwargs()
safe_url = redis_config.safe_url()
```

For application connections, `RepomConfig.redis_connection_kwargs()` returns the same
Redis client settings and raises `ValueError` in `prod` for a non-local host, including
Docker service names, unless `REDIS_ALLOW_INSECURE_REMOTE=true`. `localhost` and
loopback IP addresses remain allowed. The opt-in is only for deployments where a
tunnel or private network protects transport; Redis AUTH still crosses that path in
plaintext. `RedisConfig.connection_kwargs()` and `url()` keep their existing behavior
and do not apply this production guard.

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
├── .env                          # REDIS_PASSWORD の secrets（0600）
└── redis_init/
    └── redis.conf                # secret を含まない（password は環境変数経由で渡す）
```

設定の正本は `CONFIG_HOOK` と環境変数です。生成物を手編集しても、次の
`redis_generate` で上書きされます。

application の `ensure_running()` は停止した Redis を起動する前に、現在の設定から compose
file と `redis.conf` を書き直し、既存の `.env` をそのまま再利用します。`.env` がない場合は
通常の生成処理で作成します。複数の `EXEC_ENV` が同じ `data_path` を共有すると `.env` も
共有されるため、各環境で同じ Redis secret を設定してください。異なる実 credential が
設定されている場合は起動を拒否します。`redis_stop` と `redis_remove` も現在の設定で compose
file を書き直すため、対象環境の `EXEC_ENV` を指定してください。再生成時の secret 保護と
`--force-regenerate` は [Docker manager ガイド](../features/docker_manager_guide.md)を参照してください。

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

## 認証情報のローテーション

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
