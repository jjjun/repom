# repom Migration Guide: reusable sync transaction API (2026-03-19)

## 対象

- repom を利用している下流パッケージ
- task / worker / CLI / batch で DB transaction を `with` 文で扱うコード

## 変更概要

repom に `get_reusable_sync_transaction()` が追加されました。

- 目的: `with` 文で使える public API を提供し、private API 依存を解消する
- 契約: commit / rollback は transaction context manager と同等
- 重要: `get_standalone_sync_transaction()` と異なり、exit 時に engine dispose しない

## 推奨方針（用途別）

1. FastAPI Depends
- 継続して `get_db_session()` / `get_db_transaction()` を使用
- これらは generator 契約であり、`with` 文には使わない

2. 複数 transaction を繰り返す処理（task/worker/CLI/batch）
- `get_reusable_sync_transaction()` を使用

3. one-shot script（処理終了時に engine dispose したい）
- `get_standalone_sync_transaction()` を使用

## 置換推奨

### 1) private API 依存の置換

Before:

```python
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    run_job(session)
```

After:

```python
from repom.database import get_reusable_sync_transaction

with get_reusable_sync_transaction() as session:
    run_job(session)
```

### 2) 誤用パターンの修正

Before (NG):

```python
from repom.database import get_db_transaction

with get_db_transaction() as session:
    run_job(session)
```

After (OK):

```python
from repom.database import get_reusable_sync_transaction

with get_reusable_sync_transaction() as session:
    run_job(session)
```

### 3) one-shot script の明示化

```python
from repom.database import get_standalone_sync_transaction

with get_standalone_sync_transaction() as session:
    run_once(session)
```

## チェックリスト（下流パッケージ）

1. `_db_manager` の import が残っていない
2. `with get_db_session()` / `with get_db_transaction()` の誤用がない
3. 反復処理は `get_reusable_sync_transaction()` に統一されている
4. one-shot script は `get_standalone_sync_transaction()` のまま運用意図と一致している
5. 該当タスクのテストが green

## grep 例（移行作業用）

```bash
rg "_db_manager\.get_sync_transaction\(|with get_db_transaction\(|with get_db_session\(" src tests
```

## 補足

- `get_db_transaction()` は FastAPI Depends 互換のため generator 契約が維持されています。
- public API を利用することで、private 実装の将来変更に対する追従コストを下げられます。
