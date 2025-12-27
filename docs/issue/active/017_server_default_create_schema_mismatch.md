# Issue #017: server_default を持つカラムが create スキーマで必須扱いになる

**ステータス**: 🟡 提案中

**作成日**: 2025-12-27

**優先度**: 中

## 問題の説明

`BaseModelAuto.get_create_schema()` は `Column.server_default` を考慮していないため、`nullable=False` かつ `server_default` を持つカラムが Pydantic Create スキーマで必須扱いになる。DB ではサーバーデフォルトにより値が補完されるのに、API では入力必須として要求されるため、クライアントが不要な値を送る必要が生じる。

## 提案される解決策

- `get_create_schema()` のデフォルト判定に `server_default` を考慮し、サーバー側でデフォルトが設定される非 NULL カラムは必須としない。
- 併せて、`server_default` が callable か SQL 式の場合も扱えるようにテストを追加し、将来の回 regress を防ぐ。

## 影響範囲

- `repom/base_model_auto.py` (`_get_default_value` / `get_create_schema`)
- Create スキーマ生成に依存する FastAPI エンドポイント

## 実装計画

1. `server_default` が指定された非 NULL カラムを Create スキーマでオプショナル扱いにするロジックを追加。
2. SQL 式・定数の両パターンをカバーする単体テストを追加。
3. ドキュメント（README / ガイド）があれば更新。

## テスト計画

- `tests/unit_tests` にサーバーデフォルト付きカラムのスキーマ生成を検証するテストを追加し、`poetry run pytest tests/unit_tests/test_base_model_auto_server_default.py` を実行。

## 関連リソース

- `tests/unit_tests/test_base_model_auto_server_default.py`
- `repom/base_model_auto.py`
