# Redis 認証情報ローテーション

`repom.config_hooks.redis.apply_redis_env_overrides()` を呼ぶと、`REDIS_PASSWORD` は repom の Redis
設定に反映されます。生成する Redis instance はその値を service environment 経由で container に渡し、
`--requirepass` 付きで起動します。生成する `redis.conf` に password は入りません。health check は
設定済み password で認証します。

## 新規または再生成する設定

新しい data volume では password を設定して Redis file を生成します。

```bash
REDIS_PASSWORD="new-password" uv run redis_generate
```

Redis を起動します。

```bash
REDIS_PASSWORD="new-password" uv run redis_start
```

既存 volume の password は `redis_rotate_password` で変更します。生成済み `.env` と設定値を扱う際の
secret 保護および再生成については[Docker manager ガイド](../features/docker_manager_guide.md)を
参照してください。

接続例:

```bash
REDISCLI_AUTH="new-password" redis-cli -p 6379
```

## 起動中 instance の password 変更

`main_rotate_password(argv)` は明示的な引数 list を受け取ります。独自の option parser を使う task
runner は `rotate_redis_password_cli(...)` を keyword 引数で呼び出すと、console command と同じ
password prompt、stdin、execute safeguard を使えます。

まず runtime password 変更を dry-run します。

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run redis_rotate_password \
  --new-password-stdin \
  --old-password-stdin
```

確認後に実行します。

```bash
printf '%s\n%s\n' 'new-password' 'old-password' | uv run redis_rotate_password \
  --new-password-stdin \
  --old-password-stdin \
  --execute
```

標準入力が TTY の場合、new-password option を省略すると新しい password を prompt し、old-password
option を省略すると現在の password を prompt します。`--new-password` と `--old-password` は互換性の
ため引き続き使えますが、process argument に値が見えます。`--allow-config-password` は設定済み password
を新しい値として使う明示的な opt-in です。複数の stdin option を使う場合、新しい password を先に読みます。

非 TTY で `--execute` を指定する場合は `--old-password` または `--old-password-stdin` が必要です。
どちらも省略すると `ValueError` になります。password を設定していない Redis instance を非対話で
rotation する場合は、現在の password として空行を `--old-password-stdin` に渡します。

```bash
printf '%s\n%s\n' 'new-password' '' | uv run redis_rotate_password \
  --new-password-stdin \
  --old-password-stdin \
  --execute
```

実行前に設定値を先に更新してください。Redis が変更を確認した後に限り、repom は compose file と
`.env` secrets file を新しい password で再生成します。変更後の `.env` には以前の file が
`.env.bak` として残ります。library function `repom.redis.manage.rotate_password` も成功後に
`.env` を更新するため、呼び出し側での追加保存は不要です。

runtime command は `--old-password`、`--old-password-stdin`、または TTY prompt から得た旧 password を
`REDISCLI_AUTH` 経由で渡し、新しい password は stdin から送ります。`REDISCLI_AUTH` は mode `0600` の
一時 file に書かれ、`docker exec --env-file` で container に渡された後、command 終了時に削除されます。
旧 password は process argument に入りません。Redis 起動時の readiness poll は認証情報を送らずに ping
し、NOAUTH 応答を server 起動の確認として扱います。

## 注意事項

- port と `CHANGE_ME` password の設定規則は[設定ガイド](redis_manager_guide.md)を参照してください。
- 生成する Redis は常に password を必要とします。`REDIS_PASSWORD` が未設定または `CHANGE_ME` の場合、
  `redis_generate` は停止します。
- rotation の出力では password が mask されます。
- 失敗時は raw subprocess traceback の代わりに password を mask した error が送出されます。
- `CONFIG SET requirepass` は起動中 Redis にただちに反映されます。
