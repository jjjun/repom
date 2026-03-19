# Issue #053: task/CLI 向け sync transaction public API の追加

## ステータス
- **段階**: 完了
- **優先度**: 高
- **複雑度**: 中
- **作成日**: 2026-03-19
- **更新日**: 2026-03-19
- **完了日**: 2026-03-19
- **関連**: mine-py 側ドラフト `repom_issue_draft_task_sync_transaction_api.md`

## 実装進捗

### 実施済み

1. Public API 追加
- `repom/database.py` に `get_reusable_sync_transaction()` を追加
- `__all__` に export 追加

2. 誤用防止の修正
- `repom/database.py` の sync 利用例を `with get_reusable_sync_transaction()` に更新
- 内部 context manager 例を `with _db_manager.get_sync_session()` / `with _db_manager.get_sync_transaction()` へ明確化

3. ユニットテスト追加
- `tests/unit_tests/test_database.py` に `TestReusableSyncTransaction` を追加
- 契約（context manager）、commit、rollback、dispose 有無を検証

4. ガイド更新
- `docs/guides/repository/repository_session_patterns.md` の主要 with 文サンプルを public API ベースに更新

### テスト結果

1. `tests/unit_tests/test_database.py`
- **21 passed**

2. `tests/unit_tests`
- 実行完了（terminal exit code 0）

3. `tests/behavior_tests`
- **29 passed**

### 未完了

- なし（実装・回帰テスト完了、完了判定待ち）

## 受け入れ条件チェック（実装後）

1. `with get_reusable_sync_transaction() as session:` が動作する
- ✅ 実装済み（public API 追加 + unit test）

2. 成功時 commit、例外時 rollback が保証される
- ✅ unit test で検証済み

3. `get_reusable_sync_transaction()` 終了時に dispose されない
- ✅ unit test で検証済み

4. `get_standalone_sync_transaction()` の dispose 契約は維持される
- ✅ unit test で検証済み

5. FastAPI Depends 用 API の挙動（generator 契約）は維持される
- ✅ 既存契約テスト + `tests/unit_tests` 全体パス

6. ドキュメントに用途別の使い分けが明記される
- ✅ `repom/database.py` と `docs/guides/repository/repository_session_patterns.md` を更新済み

## 背景

下流プロジェクト（mine-py）で、private API `repom.database._db_manager.get_sync_transaction()` 依存を公開 API に置き換える過程で、次の問題が顕在化した。

1. `get_db_transaction()` は FastAPI Depends 向け generator のため、`with` 文で使うと `TypeError` になる
2. 応急対応として `get_standalone_sync_transaction()` を使うと、transaction ごとに `dispose_sync()` が走り、複数 transaction を張る task/CLI でオーバーヘッドが大きい

この Issue では、private API 依存を解消しつつ、task/CLI の multi-transaction ユースケースを性能劣化なく扱える公開 API を整備する。

## 現状実装の確認結果

`repom/database.py` の現状を確認し、以下を事実として整理する。

1. `get_db_transaction()` は public generator 関数
- FastAPI Depends 互換のため generator protocol を提供しており、context manager ではない

2. `DatabaseManager.get_sync_transaction()` は context manager
- commit/rollback を管理し、終了時は session close のみ（dispose なし）
- ただし public 関数としては未公開で、`_db_manager` 経由の private 利用が前提になっている

3. `get_standalone_sync_transaction()` は public context manager
- 内部で `DatabaseManager.get_standalone_sync_transaction()` を呼び、終了時に `dispose_sync()` を実行
- one-shot script には適するが、loop で繰り返す task では不利

4. ドキュメントの不整合が残存
- `repom/database.py` モジュール docstring に `with get_db_transaction()` 例があり、誤用を誘発
- ガイド内でも private `_db_manager` 直利用が推奨に近い形で残っている

5. テストギャップ
- `get_standalone_async_transaction()` の dispose 挙動テストはある
- sync 側 standalone dispose 挙動や、task/CLI 用 public context manager の契約テストは不足

## 方針（repom 向け）

### API 分離を明確化

用途別に API 契約を固定する。

1. `get_db_transaction()`
- FastAPI Depends 専用 generator（現状維持）

2. `get_reusable_sync_transaction()`（新設）
- task/worker/CLI 向け public context manager
- commit/rollback は `get_sync_transaction()` と同等
- **dispose しない**（engine 再利用）

3. `get_standalone_sync_transaction()`
- one-shot script 向け context manager
- 終了時 dispose（現状維持）

### 命名理由

- `reusable` により、特定用途（task）に限定せず、CLI/worker/batch など複数 transaction を張る用途へ横断的に使えることを示す
- `standalone`（one-shot, dispose あり）との対比で、engine 再利用（dispose なし）の契約を明確にできる
- async 側は現時点で同要求が明確でないため、まず sync API のみ追加し、将来必要なら対称 API を検討する

## 実装計画

### Phase 1: Public API 追加

対象: `repom/database.py`

1. `get_reusable_sync_transaction()` を追加
2. 実装は `_db_manager.get_sync_transaction()` の wrapper とし、dispose を行わない
3. docstring で「FastAPI Depends では使わない」「long-running task/CLI 向け」を明記

### Phase 2: ドキュメント整備（誤用防止）

対象: `repom/database.py`, `docs/guides/repository/repository_session_patterns.md`, 必要に応じて `README.md`

1. `with get_db_transaction()` など誤用例を修正
2. 用途別 API 早見表を追加
3. private `_db_manager` 直利用の推奨文を公開 API ベースへ寄せる

### Phase 3: テスト追加

対象: `tests/unit_tests/test_database.py`（必要なら新規 test ファイル分離）

1. API 契約テスト
- `get_db_transaction()` は generator（with 不可）
- `get_reusable_sync_transaction()` は context manager（with 可）

2. transaction 動作テスト
- 正常系 commit
- 例外時 rollback

3. lifecycle テスト
- `get_reusable_sync_transaction()` 利用後も manager の sync engine が保持される（dispose されない）
- `get_standalone_sync_transaction()` は従来通り dispose される

4. 回帰テスト
- FastAPI Depends 互換（既存テスト）を維持

### Phase 4: 公開面の仕上げ

1. 必要なら `repom/database.py` の public API セクション整理
2. changelog/issue ドキュメントへ移行ガイド追記
- `with get_db_transaction()` は不可
- `with` が必要なら `get_reusable_sync_transaction()`（反復 transaction）または `get_standalone_sync_transaction()`（one-shot）

## 受け入れ条件

1. `with get_reusable_sync_transaction() as session:` が動作する
2. 成功時 commit、例外時 rollback が保証される
3. `get_reusable_sync_transaction()` 終了時に dispose されない
4. `get_standalone_sync_transaction()` の dispose 契約は維持される
5. FastAPI Depends 用 API の挙動（generator 契約）は維持される
6. ドキュメントに用途別の使い分けが明記される

## テスト実行計画

1. `poetry run pytest tests/unit_tests/test_database.py`
2. 必要に応じて `poetry run pytest tests/unit_tests/test_async_database.py`
3. 回帰確認として `poetry run pytest tests/unit_tests`

## リスクと対策

1. 命名の誤解リスク
- 対策: docstring とガイドで `reusable=反復 transaction`, `standalone=one-shot` を明文化

2. 下流での private API 依存が残るリスク
- 対策: migration note で置換先を明示し、公開 API へ誘導

3. テスト不足による契約破壊リスク
- 対策: generator/context manager の型契約テストを追加し、FastAPI 互換回帰を固定

## 参考

- mine-py ドラフト: task/CLI での性能劣化観測（`dispose_sync()` 起因）
- 既存 Issue: `docs/issue/completed/001_fastapi_depends_fix.md`
