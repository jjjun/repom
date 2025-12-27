# Issue #017: server_default を持つカラムが create スキーマで必須扱いになる

**ステータス**: 🟢 解決済み

**作成日**: 2025-12-27

**優先度**: 中

## 問題の説明

`BaseModelAuto.get_create_schema()` は `Column.server_default` を考慮していないため、`nullable=False` かつ `server_default` を持つカラムが Pydantic Create スキーマで必須扱いになる。DB ではサーバーデフォルトにより値が補完されるのに、API では入力必須として要求されるため、クライアントが不要な値を送る必要が生じる。

## 実施した解決策

- `get_create_schema()` の必須判定を `_is_required_for_create()` に切り出し、`info` の明示設定 → `col.default` → `col.server_default` → `nullable` の優先順で判定するよう整理。
- `server_default` を持つ非 NULL カラムを Optional かつ `default=None` として扱い、入力不要であることをスキーマに反映。
- 文字列定数・SQL 式・callable（`func.now()`）の `server_default` ケースをパラメタライズしたユニットテストで、Create スキーマが必須扱いしないことを検証。

## 影響範囲

- `repom/base_model_auto.py` (`_get_default_value` / `get_create_schema`)
- Create スキーマ生成に依存する FastAPI エンドポイント

## テスト計画

- `tests/unit_tests` にサーバーデフォルト付きカラムのスキーマ生成を検証するテストを追加し、`poetry run pytest tests/unit_tests/test_base_model_auto_server_default.py` を実行。完了。

## 関連リソース

- `tests/unit_tests/test_base_model_auto_server_default.py`
- `repom/base_model_auto.py`
