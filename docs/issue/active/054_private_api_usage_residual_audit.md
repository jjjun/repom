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

## 受け入れ条件

1. `base_repository_guide.md` の private 利用例が解消される
- **達成（2026-03-19）**
2. 利用者向け主要ガイドで private 推奨が残らない
- **Phase 1 対象ガイドで達成（2026-03-19）**
3. テスト側 private 利用の棚卸し結果が文書化される
- **未着手（Phase 2 で対応予定）**

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

- この Issue は「調査結果の登録と是正方針の明文化」を目的とする。
- 実装修正は本 Issue に紐づけて段階実施する。
