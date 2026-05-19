# Issue #68: `format_size` / `get_backups` を `_backup_utils.py` へ集約

**ステータス**: 🔴 未着手

**作成日**: 2026-05-19

**優先度**: 低

## 問題の説明

バックアップサイズ表示と一覧取得のロジックが `db_backup.py` と `db_restore.py` で重複/分散している。

- [repom/scripts/db_restore.py:27-36](../../../repom/scripts/db_restore.py#L27-L36) — `format_size(size_bytes)` を定義
- [repom/scripts/db_backup.py:126](../../../repom/scripts/db_backup.py#L126) と [repom/scripts/db_backup.py:209](../../../repom/scripts/db_backup.py#L209) — 同じ `size_bytes / (1024 * 1024):.2f` を直書きでログ出力
- [repom/scripts/db_restore.py:39-65](../../../repom/scripts/db_restore.py#L39-L65) — `get_backups(backup_dir)` が `config.db_type` ベースで glob パターンを切り替え。`rotate_backups()` と同種のユーティリティだが `_backup_utils.py` に集約されていない

#063 で `rotate_backups()` だけが `_backup_utils.py` に切り出されたが、関連ユーティリティが残っている。

## 提案される解決策

`repom/scripts/_backup_utils.py` に以下を追加:

```python
def format_size(size_bytes: int) -> str:
    """Format byte count as `<x.xx> MB`."""
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def get_backups(backup_dir: str, db_type: str) -> list[Path]:
    """Return backup files matching the given db_type, newest first."""
```

- `db_restore.py` の `format_size` / `get_backups` を削除し import に置換
- `db_backup.py` の MB 計算を `format_size()` 呼び出しに置換

## 影響範囲

- [repom/scripts/_backup_utils.py](../../../repom/scripts/_backup_utils.py)
- [repom/scripts/db_backup.py](../../../repom/scripts/db_backup.py)
- [repom/scripts/db_restore.py](../../../repom/scripts/db_restore.py)
- 関連テスト: `tests/unit_tests/scripts/`（既存があれば更新、なければ最小限の境界ケースを追加）

## 実装計画

1. `_backup_utils.py` に `format_size()` と `get_backups()` を追加
2. `db_restore.py` 側の重複定義を削除、import に置換
3. `db_backup.py` のインライン MB 表記を `format_size()` 呼び出しに置換
4. 既存テストを実行し回帰がないか確認

## テスト計画

- `format_size()`: 0、1MB 未満、1MB、複数 MB の境界値テスト
- `get_backups()`: sqlite/postgres それぞれで適切なファイルのみ返ること、空ディレクトリで `[]` を返すこと
- `uv run pytest tests/unit_tests` 全件パス

## 関連リソース

- 関連完了 Issue: #063（`rotate_backups` の切り出し）
- 関連 Issue: #049, #050
