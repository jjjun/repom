# テストガイド一覧

- [テスト方針と共通 fixture](testing_guide.md)
- [fixture の詳細と例](fixture_guide.md)

共通 fixture は transaction rollback でテストを分離します。通常の repository test では
[`tests/fixtures/models`](../../../tests/fixtures/models) の model を使い、アプリケーション固有の
test model は利用側プロジェクトに定義してください。

PostgreSQL 統合テストを実行するには、`CONFIG_HOOK=repom.config_hook:hook_config`、
`EXEC_ENV=test`、`DB_TYPE=postgres`、`POSTGRES_PASSWORD` を設定し、
`127.0.0.1:5433` で PostgreSQL を起動してください。条件を満たさない場合、この統合テストは
skip されます。

```bash
uv run pytest
uv run pytest tests/unit_tests
uv run pytest tests/behavior_tests
uv run pytest tests/integration_tests
```
