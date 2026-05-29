# Issue #055: AutoDateTime のタイムゾーン非対応による naive datetime 返却

## ステータス
- **段階**: ✅ 完了
- **優先度**: 高
- **複雑度**: 中
- **作成日**: 2026-04-22
- **更新日**: 2026-04-22
- **関連**: fast-domain Proposal #004 / mine-py Issue #115

## 問題の説明

repom の `AutoDateTime` は `impl = DateTime`（timezone 指定なし）で実装されており、
`created_at` / `updated_at` が naive datetime として保存・返却される。

その結果、下流パッケージ（fast-domain / mine-py）の API で日時が以下の形式になり得る。

- 問題例: `2026-04-22T10:30:00`（タイムゾーン情報なし）
- 期待値: `2026-04-22T10:30:00+00:00`（UTC 明示）

`AutoDateTime` は `BaseModel` 系で横断的に使われるため、影響範囲が広い。

## 現状調査（repom 内で確認）

### 1) AutoDateTime 実装

対象: `repom/custom_types/AutoDateTime.py`

- `impl = DateTime`（`DateTime(timezone=True)` ではない）
- `process_bind_param()` の `None` 補完が `datetime.now()`（naive）
- `process_result_value()` は値をそのまま返し、`tzinfo` を補完しない

### 2) updated_at 自動更新イベント

対象: `repom/models/base_model.py`

- `before_update` イベントで `target.updated_at = datetime.now()` を使用
- ここでも naive datetime が生成される

### 3) 既存テストの観点

対象: `tests/unit_tests/custom_types/test_createdat.py`

- `created_at <= datetime.now()` など naive 前提の比較がある
- `tzinfo` 有無や UTC 正規化を検証するテストは未整備

## 根本原因

1. `AutoDateTime` が timezone-aware カラム/値を前提にしていない
2. `datetime.now()` の使用箇所が複数あり、naive datetime を誘発する
3. 読み出し時の `tzinfo` 補完がないため、既存データも naive のまま流通する

## 提案される解決策

### 方針

- `AutoDateTime.impl` を `DateTime(timezone=True)` へ変更
- `process_bind_param()`
  - `None` は `datetime.now(timezone.utc)` で補完
  - naive datetime 入力は UTC とみなして `tzinfo=timezone.utc` を付与
- `process_result_value()`
  - DB から取得した naive datetime は UTC として補完

### 互換性の考え方

- 移行期に naive 値が入力されても破壊的変更にならないよう、bind 時に UTC 補完する
- 既存レコード読込時も result 側で UTC 補完し、API 出力の一貫性を担保する

## 影響範囲

### repom

- `repom/custom_types/AutoDateTime.py` の型挙動変更
- `repom/models/base_model.py` の `updated_at` 更新ロジック（時刻生成）見直し要否
- `tests/unit_tests/custom_types/test_createdat.py` ほか日時比較テストの見直し
- Alembic 自動生成時の DateTime 定義差分（新規生成分）

### downstream（参考）

- fast-domain / mine-py の `created_at` / `updated_at` 応答形式へ直接影響
- PostgreSQL では `timestamp without time zone` 既存列の型変換マイグレーションが必要

## 実装計画（案）

1. `AutoDateTime` を timezone-aware 実装へ更新 ✅
2. `BaseModel` の `before_update` で UTC aware datetime を使用 ✅
3. 既存テストを timezone-aware 前提へ更新 ✅
4. SQLite / PostgreSQL の双方で unit test を実行し回帰確認 ✅（unit_tests 実施）
5. 必要に応じて migration guidance を docs に追加 ⏳

## テスト計画

- 単体テスト追加/更新:
  - naive 入力時に UTC 補完される
  - aware 入力が保持される
  - result で naive 値が UTC 補完される
  - `updated_at` 自動更新が aware 値を設定する
- 既存ユニットテスト回帰:
  - `poetry run pytest tests/unit_tests`

## 実装結果（2026-04-22）

- fast-domain 側で動作確認が完了し、実運用想定の呼び出しで問題なく実行できることを確認。

### 変更済みファイル

- `repom/custom_types/AutoDateTime.py`
  - `impl = DateTime(timezone=True)` へ変更
  - `process_bind_param`: `None` を `datetime.now(timezone.utc)` で補完
  - `process_bind_param`: naive datetime 入力を UTC として補完
  - `process_result_value`: naive datetime 取得時に UTC 補完

- `repom/models/base_model.py`
  - `before_update` イベントで `datetime.now(timezone.utc)` を使用

- `tests/unit_tests/custom_types/test_createdat.py`
  - timezone-aware 前提に既存テストを更新
  - bind/result の UTC 正規化テストを追加

### テスト結果

- 対象テスト: `tests/unit_tests/custom_types/test_createdat.py` + `tests/unit_tests/test_base_model_uuid.py`
  - **24 passed, 0 failed**
- 回帰テスト: `poetry run pytest tests/unit_tests`
  - **831 passed, 10 skipped**

## 関連ファイル

- `repom/custom_types/AutoDateTime.py`
- `repom/models/base_model.py`
- `tests/unit_tests/custom_types/test_createdat.py`
- `alembic/versions/dbdcc59b0b68_comment.py`

## 補足（スコープ外）

- downstream 固有カラム（例: fast-domain の task log 系日時カラム）は本 Issue では対象外
- 本 Issue は repom 側の共通基盤修正を対象とする
