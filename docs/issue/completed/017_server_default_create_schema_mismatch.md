# Issue #017: server_default を持つカラムが create スキーマで必須扱いになる

**ステータス**: ✅ 解決済み（レビュー完了・テスト追加・バグ修正）

**作成日**: 2025-12-27

**優先度**: 中

**レビュー日**: 2025-12-27

## 問題の説明

`BaseModelAuto.get_create_schema()` は `Column.server_default` を考慮していないため、`nullable=False` かつ `server_default` を持つカラムが Pydantic Create スキーマで必須扱いになる。DB ではサーバーデフォルトにより値が補完されるのに、API では入力必須として要求されるため、クライアントが不要な値を送る必要が生じる。

## 実施した解決策

- `get_create_schema()` の必須判定を `_is_required_for_create()` に切り出し、`info` の明示設定 → `col.default` → `col.server_default` → `nullable` の優先順で判定するよう整理。
- `server_default` を持つ非 NULL カラムを Optional かつ `default=None` として扱い、入力不要であることをスキーマに反映。
- 文字列定数・SQL 式・callable（`func.now()`）の `server_default` ケースをパラメタライズしたユニットテストで、Create スキーマが必須扱いしないことを検証。

## レビュー結果

### ✅ 実装の確認
1. **`_is_required_for_create()` メソッド**: 正しく実装されている
   - 優先順位: info → col.default → col.server_default → nullable
   
2. **`_get_default_value()` メソッド**: 正しく実装されている
   - client-side default を優先的に返す
   - server_default は None を返す（DB側で補完されるため）

3. **🐛 バグ発見と修正**: `get_create_schema()` の処理順序に問題あり
   - **問題**: `col.server_default` チェックが `default_value` チェックより先だった
   - **影響**: `col.default` と `col.server_default` 両方ある場合、server_default が優先されてしまう
   - **修正**: 処理順序を変更し、`default_value is not None` を先にチェック

### ✅ テストの網羅性

**元のテスト（4件）**:
- ✅ `server_default` がある非 NULL カラム（literal, sql_text, callable）
- ✅ DB でのデフォルト値適用確認

**追加したテスト（5件）**:
- ✅ `server_default` + `nullable=True` の組み合わせ
- ✅ `server_default` + `col.default` の組み合わせ（優先度テスト）
- ✅ `info={'create_required': True}` で明示的にオーバーライド
- ✅ Update スキーマへの影響確認
- ✅ Response スキーマへの影響確認

**合計**: 9件のテスト（全て成功 ✅）

## 影響範囲

- `repom/base_model_auto.py` 
  - `_get_default_value()` メソッド
  - `get_create_schema()` メソッド（処理順序修正）
  - `_is_required_for_create()` メソッド
- Create スキーマ生成に依存する FastAPI エンドポイント

## 修正内容

### バグ修正
```python
# 修正前（誤り）:
if col.server_default is not None:
    # server_default が優先されてしまう
    ...

if default_value is None:
    ...
else:
    # col.default があっても実行されない
    ...

# 修正後（正しい）:
if default_value is not None:
    # col.default を優先
    field_definitions[col.name] = (
        python_type,
        Field(default=default_value, **field_kwargs)
    )
    continue

if col.server_default is not None:
    # server_default のみの場合
    ...
```

## テスト結果

```bash
$ poetry run pytest tests/unit_tests/test_base_model_auto_server_default.py -v
===================== 9 passed in 0.11s =====================

$ poetry run pytest tests/unit_tests/test_base_model_auto*.py -v  
===================== 39 passed in 0.30s =====================
```

## 関連リソース

- `tests/unit_tests/test_base_model_auto_server_default.py` (9 tests)
- `repom/base_model_auto.py` (修正済み)
