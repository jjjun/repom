# Issue #63: `db_backup.py` の SQLite/PostgreSQL ローテーション処理の共通化

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 低

## 問題の説明

`repom/scripts/db_backup.py` 内で、SQLite バックアップと PostgreSQL バックアップそれぞれに同じバックアップローテーション処理（古いバックアップを N 件残して削除）が重複している。

監査時の参照位置:
- SQLite 側: db_backup.py 内のローテーション処理
- PostgreSQL 側: 同ファイル内の別ブロックに同形ロジック

`max_backups` で件数制御し、`sorted(..., key=lambda p: p.stat().st_mtime)` で古い順に削除、という典型処理が DB タイプごとに書かれている。

## 提案される解決策

`repom/scripts/_backup_utils.py`（新規）または `repom/scripts/db_backup.py` 内のプライベート関数として共通化:

```python
def rotate_backups(backup_dir: Path, glob_pattern: str, max_keep: int) -> None:
    files = sorted(backup_dir.glob(glob_pattern), key=lambda p: p.stat().st_mtime)
    for old in files[:-max_keep] if max_keep > 0 else []:
        old.unlink()
```

SQLite / PostgreSQL の双方からこのヘルパを呼び、glob パターンと保持数だけを渡す。

## 影響範囲

- `repom/scripts/db_backup.py`
- 新規（または既存共有モジュールへ追加）: 共通ヘルパ
- テスト: `tests/unit_tests/scripts/` 配下に対応するテスト

## 実装計画

1. db_backup.py 内のローテーション箇所を 2 箇所特定
2. 共通ヘルパ関数を実装
3. SQLite / PostgreSQL 経路から共通ヘルパを呼ぶよう置換
4. ローテーション単体テストを追加（保持数 0, 1, N、ファイルが少ない場合等）

## テスト計画

- 新規 unit test: rotate_backups の境界ケース
- 既存 db_backup 周りのテスト全件パス
- 手動: `uv run db_backup` でバックアップ生成と古いファイル削除を確認

## 関連リソース

- [repom/scripts/db_backup.py](../../../repom/scripts/db_backup.py)
- [repom/scripts/db_restore.py](../../../repom/scripts/db_restore.py)（参考: 復元側ロジック）
- 関連完了 Issue: #048, #049, #050
