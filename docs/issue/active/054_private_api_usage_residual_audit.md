# Issue #054: ガイド・テスト内の private API 利用残存の整理

## ステータス
- **段階**: 進行中
- **優先度**: 中
- **複雑度**: 低
- **作成日**: 2026-03-19
- **関連 Issue**: #053

## 問題の説明

repom 利用パッケージ側から、次の指摘を受領した。

1. ガイドの一部に private 利用例が残っている
- 例: `docs/guides/repository/base_repository_guide.md:85`

2. 一部テストが内部検証目的で private API を使用している
- 直ちにブロッカーではないが、運用上の整理対象

## 調査結果（確認済み）

### A. ガイド側

1. 指摘箇所は再現確認済み
- `docs/guides/repository/base_repository_guide.md` に `_db_manager` 利用例が残存

2. 同系統の残存箇所あり
- `docs/guides/features/query_analyzer_guide.md`
- `docs/guides/repository/async_repository_guide.md`
- `docs/guides/repository/repository_session_patterns.md`（async セクション中心）

3. 例外的に許容される記述
- `docs/guides/tmp/repom_reusable_sync_transaction_migration_guide_2026-03-19.md` は「Before/After の置換説明」のため、Before 側に private 例を意図的に記載

### B. テスト側

1. private API 利用は複数箇所で確認
- `tests/unit_tests/test_database.py`
- `tests/unit_tests/test_async_database.py`
- `tests/unit_tests/test_external_session_commit.py`
- `tests/behavior_tests/test_unique_key_handling.py`

2. 判定
- 現時点では内部契約検証/manager 挙動確認の文脈であり、**即時ブロッカーではない**

## 期待される状態

1. 利用者向けガイドは public API 優先の記述に統一される
2. private API の記述が必要な場合は「内部検証用途」であることを明示する
3. テスト側の private 利用は段階的に棚卸しし、public API で代替可能なものから移行する

## 対応方針（提案）

### Phase 1: ドキュメント是正（優先）

1. `docs/guides/repository/base_repository_guide.md` の private 例を public API に置換
2. `docs/guides/features/query_analyzer_guide.md` の利用例を見直し
3. `docs/guides/repository/async_repository_guide.md` と `docs/guides/repository/repository_session_patterns.md` の async セクションを整理

### Phase 1 実施状況（2026-03-19）

実施済み:
1. `docs/guides/repository/base_repository_guide.md`
- `_db_manager.get_sync_transaction()` を `get_reusable_sync_transaction()` に置換
- 用途別 API 使い分け（FastAPI Depends / sync 反復 transaction / one-shot / async）を追記

2. `docs/guides/features/query_analyzer_guide.md`
- `_db_manager.get_sync_session()` を public API ベースに置換
- スクリプト例は one-shot 向けに `get_standalone_sync_transaction()` へ変更

3. `docs/guides/repository/async_repository_guide.md`
- 同期版比較コードの `_db_manager` 参照を削除し、`get_reusable_sync_transaction()` に統一

4. `docs/guides/repository/repository_session_patterns.md`
- async セクションを含む残存 private 記述を public API に置換
- 用途別クイックマップを追加（FastAPI Depends / sync with / one-shot / async）
- 手動管理の説明を public API (`get_async_db_transaction()` + `dispose_engines()`) ベースに更新

### Phase 2: テスト棚卸し

1. テスト内 `_db_manager` 利用を「必須/置換可能」に分類
2. 置換可能なものから public API に順次移行
3. 置換しないものはコメントで理由を明記

### Phase 2 棚卸し結果（2026-03-19）

#### 対象ファイル（要修正）

1. `tests/unit_tests/test_external_session_commit.py`
- 現状: `_db_manager.get_sync_transaction()` を複数箇所で利用
- 判定: **置換可能**
- 置換方針: `get_reusable_sync_transaction()` に統一

2. `tests/unit_tests/test_database.py`
- 現状: `_db_manager.get_sync_session()` / `_db_manager.get_sync_transaction()` / `_db_manager.get_inspector()` を利用
- 判定: **置換可能（大半）**
- 置換方針:
  - transaction 文脈は `get_reusable_sync_transaction()` へ
  - inspector は `get_inspector()` へ
  - manager 挙動検証は `DatabaseManager()` インスタンス経由で継続（public メソッドの契約検証として許容）

3. `tests/unit_tests/test_async_database.py`
- 現状: `_db_manager.get_async_session()` / `_db_manager.get_async_transaction()` / `_db_manager.get_standalone_async_transaction()` を利用
- 判定: **置換可能（大半）**
- 置換方針:
  - standalone は `get_standalone_async_transaction()` に置換
  - FastAPI Depends 互換テストのメッセージ内 private 文言を public API ベースに修正
  - manager 直接検証が必要な箇所は `DatabaseManager()` インスタンス経由へ寄せる

4. `tests/behavior_tests/test_unique_key_handling.py`
- 現状: import に `_db_manager` が残存（実利用なし）、説明コメントに private 参照
- 判定: **置換可能**
- 置換方針: `_db_manager` import を削除し、コメントを `db_test` ベースの説明に更新

#### 1周目（Phase 2 - Round 1）実施対象

1. `tests/unit_tests/test_external_session_commit.py`（全面置換しやすく影響が局所的）
2. `tests/behavior_tests/test_unique_key_handling.py`（import/comment の軽微修正）
3. `tests/unit_tests/test_database.py`（明確な置換箇所を先行対応）
4. `tests/unit_tests/test_async_database.py`（範囲が広いので round 1 では public API 直置換可能部分を優先）

#### Round 1 の完了条件（提案）

1. 上記4ファイルで module-level `_db_manager` import を解消
2. public API で代替可能な呼び出しを置換
3. manager 挙動の内部契約テストは `DatabaseManager()` インスタンス経由に明示化
4. `poetry run pytest tests/unit_tests/test_database.py tests/unit_tests/test_external_session_commit.py tests/unit_tests/test_async_database.py tests/behavior_tests/test_unique_key_handling.py` が通過

## 受け入れ条件

1. `base_repository_guide.md` の private 利用例が解消される
- **達成（2026-03-19）**
2. 利用者向け主要ガイドで private 推奨が残らない
- **Phase 1 対象ガイドで達成（2026-03-19）**
3. テスト側 private 利用の棚卸し結果が文書化される
- **達成（2026-03-19）**
4. テスト側 private API 利用が public API または `DatabaseManager()` インスタンス経由に置換される
- **Phase 2 Round 1 達成（2026-03-19）** — 4ファイル修正、63 passed

## 影響範囲

- `docs/guides/repository/base_repository_guide.md`
- `docs/guides/features/query_analyzer_guide.md`
- `docs/guides/repository/async_repository_guide.md`
- `docs/guides/repository/repository_session_patterns.md`
- `tests/unit_tests/test_database.py`
- `tests/unit_tests/test_async_database.py`
- `tests/unit_tests/test_external_session_commit.py`
- `tests/behavior_tests/test_unique_key_handling.py`

## 備考

- 実装修正は本 Issue に紐づけて段階実施する。
