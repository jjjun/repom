# Issue #050: バックアップディレクトリの DB タイプ別分離

**ステータス**: ✅ 完了

**作成日**: 2026-02-25

**完了日**: 2026-02-25

**優先度**: 中

**関連 Issue**: [#048 PostgreSQL スクリプト対応](../completed/048_postgresql_script_support.md), [#049 Docker ベース pg_dump/pg_restore](../completed/049_docker_based_pg_dump_restore.md)

## 問題の説明

現在、`db_restore` コマンドでリストア対象を選択する際、SQLite と PostgreSQL のバックアップファイルが混在して表示されます。

### 再現例

PostgreSQL 環境で `poetry run db_restore` を実行した場合：

```
Available backups:
────────────────────────────────────────────────────────────
[1] db_20260225_000317.sql.gz (0.00 MB) - 2026-02-25 00:03:17 <- latest
[2] repom_dev_20260224_232101.sqlite3 (0.00 MB) - 2026-02-24 23:20:54
[3] repom_dev_20260224_232126.sqlite3 (0.00 MB) - 2026-02-24 23:20:54
[4] db.dev_20260207_163847.sqlite3 (0.02 MB) - 2026-01-31 17:15:59
[5] db.dev_20260207_164124.sqlite3 (0.02 MB) - 2026-01-31 17:15:59
────────────────────────────────────────────────────────────
```

**問題点**:
- PostgreSQL 環境で SQLite のバックアップファイルが表示される
- SQLite 環境で PostgreSQL のバックアップファイルが表示される
- 誤って異なる DB タイプのバックアップを選択すると不具合が発生する

### 根本原因

**1. バックアップディレクトリが単一**:
```python
# repom/config.py (Lines 415-420)
@property
def db_backup_path(self) -> Optional[str]:
    """バックアップディレクトリ - デフォルトで data_path/backups"""
    if self._db_backup_path is not None:
        return self._db_backup_path
    if self.data_path:
        return str(Path(self.data_path) / 'backups')
    return None
```

現在: `data/repom/backups/` に全てのバックアップファイルが混在

**2. リストア時のフィルタリングなし**:
```python
# repom/scripts/db_restore.py (Lines 46-61)
def get_backups(backup_dir: str) -> List[Path]:
    """バックアップファイルを最新順に取得"""
    if not os.path.exists(backup_dir):
        return []

    backup_path = Path(backup_dir)

    # SQLite と PostgreSQL 両方のバックアップファイルを検出
    sqlite_backups = list(backup_path.glob("*.sqlite3"))
    postgres_backups = list(backup_path.glob("db_*.sql.gz"))

    all_backups = sqlite_backups + postgres_backups  # ← 全て返してしまう

    # 最新順にソート（作成日時の降順）
    all_backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    return all_backups
```

現在: すべてのバックアップファイル（SQLite + PostgreSQL）を返している

## 提案される解決策

### アプローチ: DB タイプ別サブディレクトリ分離

バックアップディレクトリを DB タイプごとに分離します：

```
data/repom/backups/
├── sqlite/          # SQLite バックアップ専用
│   ├── repom_dev_20260224_232101.sqlite3
│   └── repom_dev_20260224_232126.sqlite3
└── postgres/        # PostgreSQL バックアップ専用
    └── db_20260225_000317.sql.gz
```

**メリット**:
1. ✅ **ファイルシステムレベルで完全分離** - 誤選択リスクゼロ
2. ✅ **将来の拡張性** - MySQL, MongoDB などの追加が容易
3. ✅ **明確な構造** - どの DB タイプのバックアップか一目瞭然
4. ✅ **既存コード変更最小** - `config.db_backup_path` の変更だけで対応可能

**他の検討案と比較**:
- ❌ **Option B: get_backups() でフィルタリング** - ファイルシステム上は混在したまま
- ❌ **Option C: ファイル名プレフィックス** - 既存バックアップとの互換性が失われる

## 実装計画

### Phase 1: config.db_backup_path の修正

**変更ファイル**: `repom/config.py`

```python
@property
def db_backup_path(self) -> Optional[str]:
    """バックアップディレクトリ - DB タイプ別にサブディレクトリ作成
    
    Returns:
        - SQLite: data_path/backups/sqlite
        - PostgreSQL: data_path/backups/postgres
    """
    if self._db_backup_path is not None:
        return self._db_backup_path
    if self.data_path:
        base_backup_path = Path(self.data_path) / 'backups'
        return str(base_backup_path / self.db_type)
    return None
```

**動作**:
- SQLite 環境: `data/repom/backups/sqlite/`
- PostgreSQL 環境: `data/repom/backups/postgres/`

### Phase 2: db_restore.py のフィルタリング強化

**変更ファイル**: `repom/scripts/db_restore.py`

```python
def get_backups(backup_dir: str) -> List[Path]:
    """バックアップファイルを最新順に取得（DB タイプに応じてフィルタリング）

    Args:
        backup_dir: バックアップディレクトリパス

    Returns:
        バックアップファイルのリスト（最新順、現在の DB タイプのみ）
    """
    if not os.path.exists(backup_dir):
        return []

    backup_path = Path(backup_dir)

    # DB タイプに応じてバックアップファイルを検出
    if config.db_type == 'sqlite':
        backups = list(backup_path.glob("*.sqlite3"))
    elif config.db_type == 'postgres':
        backups = list(backup_path.glob("db_*.sql.gz"))
    else:
        logger.warning(f"Unknown db_type: {config.db_type}, showing all backups")
        backups = list(backup_path.glob("*"))

    # 最新順にソート（作成日時の降順）
    backups.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    return backups
```

**動作**:
- Phase 1 により既に正しいディレクトリを見ているが、念のため DB タイプでフィルタリング
- 予期しない拡張子のファイルが混入しても安全

### Phase 3: 既存バックアップファイルの移行（オプション）

**対応方針**: マニュアル移行を推奨

ユーザーに既存バックアップの移動を案内：

```bash
# Windows
Move-Item data\repom\backups\*.sqlite3 data\repom\backups\sqlite\
Move-Item data\repom\backups\db_*.sql.gz data\repom\backups\postgres\

# Linux/macOS
mv data/repom/backups/*.sqlite3 data/repom/backups/sqlite/
mv data/repom/backups/db_*.sql.gz data/repom/backups/postgres/
```

**将来的な拡張案**:
- `poetry run db_migrate_backups` コマンドの追加（Issue #051 として分離）
- 自動検出 + 確認プロンプト + 移動

### Phase 4: テストとドキュメント更新

**テスト計画**:
1. SQLite 環境でバックアップ → `data/repom/backups/sqlite/` に保存されることを確認
2. PostgreSQL 環境でバックアップ → `data/repom/backups/postgres/` に保存されることを確認
3. SQLite 環境でリストア → SQLite バックアップのみ表示されることを確認
4. PostgreSQL 環境でリストア → PostgreSQL バックアップのみ表示されることを確認

**ドキュメント更新**:
- README.md: バックアップディレクトリ構造を記載
- AGENTS.md: バックアップディレクトリ構造を更新

## 影響範囲

**変更ファイル**:
- ✏️ `repom/config.py`: `db_backup_path` プロパティ修正（5 行変更）
- ✏️ `repom/scripts/db_restore.py`: `get_backups()` フィルタリング強化（15 行変更）
- 📖 `README.md`: バックアップディレクトリ構造ドキュメント追加
- 📖 `AGENTS.md`: バックアップディレクトリ構造更新

**既存機能への影響**:
- ✅ **後方互換性**: 既存バックアップは手動移行が必要（マイグレーションガイド提供）
- ✅ **SQLite/PostgreSQL 両方対応**
- ✅ **db_backup.py は変更不要**: `config.db_backup_path` を使用しているため自動対応
- ✅ **自動ディレクトリ作成**: `config.auto_create_dirs` により自動作成

## 期待される効果

### Before (現状)

**PostgreSQL 環境**:
```bash
$ poetry run db_restore

Available backups:
[1] db_20260225_000317.sql.gz (0.00 MB) - 2026-02-25 00:03:17 <- latest
[2] repom_dev_20260224_232101.sqlite3 (0.00 MB) - 2026-02-24 23:20:54  # ← 誤選択リスク
[3] repom_dev_20260224_232126.sqlite3 (0.00 MB) - 2026-02-24 23:20:54  # ← 誤選択リスク
```

**問題**: SQLite バックアップを選択すると不具合発生

### After (改善後)

**PostgreSQL 環境**:
```bash
$ poetry run db_restore

Available backups:
[1] db_20260225_000317.sql.gz (0.00 MB) - 2026-02-25 00:03:17 <- latest
```

**効果**: PostgreSQL バックアップのみ表示、誤選択不可能

**SQLite 環境**:
```bash
$ poetry run db_restore

Available backups:
[1] repom_dev_20260224_232126.sqlite3 (0.00 MB) - 2026-02-24 23:20:54 <- latest
[2] repom_dev_20260224_232101.sqlite3 (0.00 MB) - 2026-02-24 23:20:54
```

**効果**: SQLite バックアップのみ表示、誤選択不可能

## 実装スケジュール

**優先度**: 中（次回実装優先候補）

**見積もり**:
- Phase 1: config.py 修正 - 5 分
- Phase 2: db_restore.py 修正 - 10 分
- Phase 3: 既存バックアップ移行ガイド作成 - 5 分
- Phase 4: テストとドキュメント - 15 分
- **合計**: 約 35 分

## 関連リソース

- **Issue #048**: PostgreSQL スクリプト対応（完了済み）
- **Issue #049**: Docker ベース pg_dump/pg_restore（完了済み）
- **repom/config.py**: 設定クラス（Lines 415-420）
- **repom/scripts/db_backup.py**: バックアップスクリプト
- **repom/scripts/db_restore.py**: リストアスクリプト（Lines 46-61）

## 備考

### 既存バックアップの扱い

この変更により、既存バックアップファイルは新しいサブディレクトリ構造に手動で移行する必要があります。

**移行手順**:
1. `data/repom/backups/sqlite/` ディレクトリを作成
2. `data/repom/backups/postgres/` ディレクトリを作成
3. `*.sqlite3` ファイルを `sqlite/` に移動
4. `db_*.sql.gz` ファイルを `postgres/` に移動

**自動マイグレーション機能**: 将来的に Issue #051 として検討

### 将来的な拡張

この設計により、以下の DB タイプの追加が容易になります：
- `data/repom/backups/mysql/`
- `data/repom/backups/mongodb/`
- `data/repom/backups/mariadb/`
