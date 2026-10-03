# テストガイド一覧

- [テスト方針と共通 fixture](testing_guide.md)
- [fixture の詳細と例](fixture_guide.md)

共通 fixture の `db_test` / `async_db_test` は function-scoped transaction を開き、それらの session を通した
書き込みを test 後に rollback します。別 session や connection からの書き込みがこの rollback に含まれる保証はありません。
通常の repository test では
[`tests/fixtures/models`](../../../tests/fixtures/models) の model を使い、アプリケーション固有の
test model は利用側プロジェクトに定義してください。

PostgreSQL 統合テストを実行するには、`CONFIG_HOOK=repom.config_hook:hook_config`、
`EXEC_ENV=test`、`DB_TYPE=postgres`、`POSTGRES_PASSWORD` を設定し、
`127.0.0.1:5433` で PostgreSQL を起動してください。条件を満たさない場合、この統合テストは
skip されます。統合テストでは固定名の `integration_test` table を作成・削除するため、専用の
破棄可能な database を使ってください。`EXEC_ENV=test` は database の安全性を保証しません。

```bash
uv run pytest
uv run pytest tests/unit_tests
uv run pytest tests/behavior_tests
uv run pytest tests/integration_tests
```
