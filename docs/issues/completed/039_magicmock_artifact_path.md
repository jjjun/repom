# Issue: MagicMock による生成ディレクトリの配置

## Status
- **Created**: 2026-02-23
- **Completed**: 2026-02-23
- **Priority**: Medium
- **Complexity**: Low

## Problem Description
`repom.postgres.manage.config` をパッチする単体テストでは、実環境の設定読込を避けてテストを独立させるために `MagicMock` を使用しています。実装側では `get_compose_dir()` が `config.data_path` からディレクトリを構築して作成しますが、モック側で `data_path` を明示しないと `MagicMock` 自体が文字列化され、プロジェクトルートに `MagicMock/` ディレクトリが作成されます。

これは貢献者にとって混乱を招き、リポジトリルートに不要な成果物を残します。生成物が必要な場合は、Git 管理外の一時/データ保存先である `data/repom/` 配下に配置する方針とします。

なお、本件はプロダクションの不具合というより、テスト側で `mock_config.data_path` を明示しないことによる副作用です（モックの設定不足）。

## Expected Behavior
- 単体テストがプロジェクトルートにディレクトリを作成しない。
- テストでファイル出力が必要な場合は `data/repom/` 配下、または隔離された一時ディレクトリに限定する。

## Actual Behavior
- 単体テスト実行時に `config.data_path` が暗黙的に `MagicMock` として扱われ、プロジェクトルートに `MagicMock/` ディレクトリが生成される。

## Solution
- 単体テストの独立性を保つため `MagicMock` の利用は継続しつつ、`mock_config.data_path` を明示的に隔離パスへ設定する（推奨: `tmp_path / "data" / "repom"`、または `data/repom/` 配下の相当パス）。これを本件の採用方針とする。
- 代替案として、テスト側で `get_compose_dir()` をパッチし、`data/repom/` 配下の一時ディレクトリを返す。

これによりテストの独立性を維持しつつ、生成物を意図したデータディレクトリのみに配置できます。

## Test Results
- ✅ Unit tests: 671 passed, 10 skipped
- ✅ Behavior tests: 29 passed

## Related Documents
- tests/unit_tests/test_postgres_manage.py
- repom/postgres/manage.py
