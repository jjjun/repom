# PostgreSQL ガイド一覧

- [セットアップと service lifecycle](postgresql_setup_guide.md)
- [実行時環境変数](runtime_env_overrides.md)
- [認証情報ローテーション](credential_rotation.md)

有効な設定値は `CONFIG_HOOK`、`EXEC_ENV`、環境変数によって決まります。DB を操作する前に
`uv run repom_info` で接続先、port、DB 名を確認してください。

`pyproject.toml` で定義されている主な command:

```bash
uv run postgres_generate
uv run postgres_start
uv run postgres_stop
uv run postgres_remove
uv run postgres_rotate_credentials
uv run pgadmin_rotate_password
```

既存 volume の credential を変更するときは rotation command を使います。生成済み `.env` の値を
意図的に置き換える場合の `--force-regenerate` は
[Docker manager ガイド](../features/docker_manager_guide.md)を参照してください。
