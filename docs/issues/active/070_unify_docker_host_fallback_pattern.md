# Issue #70: `db_backup` / `db_restore` の Docker/host fallback パターン共通化

**ステータス**: 🔴 未着手

**作成日**: 2026-05-19

**優先度**: 低

## 問題の説明

PostgreSQL バックアップ/リストアで「Docker コンテナ起動中なら docker exec、停止中ならホスト側 CLI にフォールバック」というパターンが 2 か所に重複している。

- [repom/scripts/db_backup.py:242-259](../../../repom/scripts/db_backup.py#L242-L259) — `backup_postgresql()` が `is_container_running()` で分岐し `backup_postgresql_via_docker()` / `backup_postgresql_via_host()` を呼び分け
- [repom/scripts/db_restore.py:300-320](../../../repom/scripts/db_restore.py#L300-L320) — `restore_postgresql(backup_file)` が同じ判定で `restore_postgresql_via_docker()` / `restore_postgresql_via_host()` を呼び分け

両者ともに以下が同形:
- `container_name = config.postgres.container.get_container_name()`
- `DockerCommandExecutor.is_container_running(container_name)` で分岐
- 起動中 → docker exec 系を呼び、停止中 → ホスト CLI 系へフォールバックし warning ログ

加えて、各経路の例外処理 (`FileNotFoundError` → "docker command not found" メッセージ、`CalledProcessError` → stderr 出力) も非常に似ている。

## 提案される解決策

`repom/scripts/_backup_utils.py`（または新規 `_postgres_runner.py`）にディスパッチャを切り出す:

```python
def run_postgres_via_docker_or_host(
    *,
    via_docker: Callable[[], None],
    via_host: Callable[[], None],
    operation: str,  # "backup" / "restore" 等、ログ用
) -> None:
    container_name = config.postgres.container.get_container_name()
    if DockerCommandExecutor.is_container_running(container_name):
        logger.info(f"Container {container_name} is running, using Docker exec")
        via_docker()
    else:
        logger.warning(
            f"Container {container_name} is not running, falling back to host tools. "
            f"Consider running 'uv run postgres_start' first."
        )
        via_host()
```

加えて、`FileNotFoundError`（`docker` コマンド不在）時のメッセージ整形ヘルパも共通化候補。

## 影響範囲

- [repom/scripts/db_backup.py](../../../repom/scripts/db_backup.py)
- [repom/scripts/db_restore.py](../../../repom/scripts/db_restore.py)
- 新規共通モジュール（または `_backup_utils.py` に追加）

## 実装計画

1. ディスパッチャ関数を共通モジュールに実装
2. `db_backup.py` の `backup_postgresql()` をリファクタ
3. `db_restore.py` の `restore_postgresql()` をリファクタ
4. docker 不在時のエラー文言テスト追加

## テスト計画

- ディスパッチャ単体テスト（モック `is_container_running` で True/False/FileNotFoundError 3 ケース）
- 既存の backup/restore 関連テスト全件パス
- 手動: コンテナ起動中/停止中それぞれで `uv run db_backup` / `uv run db_restore` が期待通り分岐

## 関連リソース

- [repom/scripts/db_backup.py](../../../repom/scripts/db_backup.py)
- [repom/scripts/db_restore.py](../../../repom/scripts/db_restore.py)
- 関連完了 Issue: #049（Docker 経由 pg_dump/pg_restore）, #063（rotate_backups 共通化）
