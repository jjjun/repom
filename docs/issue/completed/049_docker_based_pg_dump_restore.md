# Issue #049: Docker コンテナベースの pg_dump/pg_restore 実装

**ステータス**: ✅ 完了

**作成日**: 2026-02-24

**完了日**: 2026-02-25

**優先度**: 中

**関連 Issue**: [#048 PostgreSQL スクリプト対応](../completed/048_postgresql_script_support.md) の継続改善

## 問題の説明

現在の実装（Issue #048）では、PostgreSQL のバックアップ・リストアにホスト環境の `pg_dump`/`psql` コマンドが必要です。

### 現状の問題点

1. **環境依存性が高い**:
   ```bash
   poetry run db_backup
   # ERROR: pg_dump command not found. Please install PostgreSQL client tools.
   ```
   - Windows ユーザーは PostgreSQL クライアントツールを別途インストール必要
   - PATH 設定が必要
   - インストール手順が煩雑

2. **バージョン不一致リスク**:
   - ホスト側の pg_dump バージョン ≠ PostgreSQL サーバーバージョン
   - 互換性問題が発生する可能性

3. **クロスプラットフォーム対応が困難**:
   - Windows/Linux/macOS でインストール方法が異なる
   - ユーザーに手動設定を強いる

### 既存の Docker 基盤

repom は既に Docker 基盤を持っており、`docker exec` を使用している実例があります：

```python
# repom/postgres/manage.py (Line 61)
subprocess.run(
    ["docker", "exec", container_name, "pg_isready", "-U", user],
    ...)
```

この実装パターンを pg_dump/pg_restore にも適用できます。

## 提案される解決策

### Docker コンテナ内の pg_dump/pg_restore を使用

**メリット**:
1. ✅ **環境非依存**: ホスト環境に PostgreSQL 不要
2. ✅ **バージョン整合性**: サーバーと pg_dump のバージョンが完全一致
3. ✅ **クロスプラットフォーム**: Docker さえあれば動作
4. ✅ **自動化可能**: コンテナが起動していれば即使用可能

**実装方針**:
```python
def backup_postgresql():
    container_name = config.postgres.container.get_container_name()
    
    # コンテナ起動確認
    if is_container_running(container_name):
        # Docker 経由で pg_dump 実行（推奨）
        backup_using_docker_exec(container_name)
    else:
        # フォールバック: ホスト側の pg_dump を試行
        backup_using_host_pg_dump()
```

### 実行コマンド例

**バックアップ（pg_dump）**:
```bash
docker exec repom_postgres pg_dump \
  -U repom \
  -d repom_dev \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  | gzip > backup.sql.gz
```

**リストア（psql）**:
```bash
gunzip -c backup.sql.gz | docker exec -i repom_postgres psql \
  -U repom \
  -d repom_dev
```

## 技術的ポイント

### 1. DockerCommandExecutor への docker exec ヘルパー追加

```python
# repom/_.docker_manager.py
class DockerCommandExecutor:
    @staticmethod
    def exec_command(
        container_name: str,
        command: list[str],
        stdin: Optional[bytes] = None,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """docker exec でコンテナ内コマンドを実行
        
        Args:
            container_name: コンテナ名
            command: 実行コマンド（リスト形式）
            stdin: 標準入力に渡すデータ
            capture_output: stdout/stderr をキャプチャするか
            
        Returns:
            subprocess.CompletedProcess
            
        Raises:
            FileNotFoundError: docker コマンド不在
            subprocess.CalledProcessError: コマンド失敗
        """
        cmd = ["docker", "exec"]
        if stdin is not None:
            cmd.append("-i")  # Interactive mode for stdin
        cmd.append(container_name)
        cmd.extend(command)
        
        return subprocess.run(
            cmd,
            input=stdin,
            capture_output=capture_output,
            check=True
        )
    
    @staticmethod
    def is_container_running(container_name: str) -> bool:
        """コンテナが起動中か確認"""
        status = DockerCommandExecutor.get_container_status(container_name)
        return status.startswith("Up")
```

### 2. db_backup.py の実装変更

```python
def backup_postgresql_via_docker():
    """Docker 経由で pg_dump 実行（推奨）"""
    container_name = config.postgres.container.get_container_name()
    
    # pg_dump コマンド構築
    pg_dump_cmd = [
        "pg_dump",
        "-U", config.postgres.user,
        "-d", config.postgres_db,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
    ]
    
    # docker exec で pg_dump 実行
    result = DockerCommandExecutor.exec_command(
        container_name=container_name,
        command=pg_dump_cmd,
        capture_output=True
    )
    
    # gzip 圧縮して保存
    with gzip.open(backup_path, 'wb') as gz_file:
        gz_file.write(result.stdout)

def backup_postgresql_via_host():
    """ホスト側の pg_dump を使用（フォールバック）"""
    # Issue #048 の現行実装
    ...

def backup_postgresql():
    """PostgreSQL バックアップのエントリーポイント"""
    container_name = config.postgres.container.get_container_name()
    
    if DockerCommandExecutor.is_container_running(container_name):
        logger.info(f"Using Docker container: {container_name}")
        backup_postgresql_via_docker()
    else:
        logger.warning(f"Container {container_name} not running, using host pg_dump")
        backup_postgresql_via_host()
```

### 3. db_restore.py の実装変更

```python
def restore_postgresql_via_docker(backup_file: Path):
    """Docker 経由で psql リストア（推奨）"""
    container_name = config.postgres.container.get_container_name()
    
    # バックアップファイルを解凍
    with gzip.open(backup_file, 'rb') as gz_file:
        sql_data = gz_file.read()
    
    # psql コマンド構築
    psql_cmd = [
        "psql",
        "-U", config.postgres.user,
        "-d", config.postgres_db,
        "-v", "ON_ERROR_STOP=1",
    ]
    
    # docker exec -i で psql 実行（stdin から SQL を注入）
    result = DockerCommandExecutor.exec_command(
        container_name=container_name,
        command=psql_cmd,
        stdin=sql_data,
        capture_output=True
    )

def restore_postgresql_via_host(backup_file: Path):
    """ホスト側の gunzip + psql を使用（フォールバック）"""
    # Issue #048 の現行実装
    ...

def restore_postgresql(backup_file: Path):
    """PostgreSQL リストアのエントリーポイント"""
    container_name = config.postgres.container.get_container_name()
    
    if DockerCommandExecutor.is_container_running(container_name):
        logger.info(f"Using Docker container: {container_name}")
        restore_postgresql_via_docker(backup_file)
    else:
        logger.warning(f"Container {container_name} not running, using host tools")
        restore_postgresql_via_host(backup_file)
```

## 影響範囲

**新規追加**:
- `repom/_.docker_manager.py`:
  - `DockerCommandExecutor.exec_command()` メソッド追加
  - `DockerCommandExecutor.is_container_running()` メソッド追加

**変更ファイル**:
- `repom/scripts/db_backup.py`:
  - `backup_postgresql()` を `backup_postgresql_via_host()` にリネーム
  - `backup_postgresql_via_docker()` 新規追加
  - `backup_postgresql()` エントリーポイント実装（Docker/Host 自動切り替え）

- `repom/scripts/db_restore.py`:
  - `restore_postgresql()` を `restore_postgresql_via_host()` にリネーム
  - `restore_postgresql_via_docker()` 新規追加
  - `restore_postgresql()` エントリーポイント実装（Docker/Host 自動切り替え）

**既存機能への影響**:
- ✅ **後方互換性 100%**: コンテナ未起動時は自動的にホスト pg_dump にフォールバック
- ✅ **SQLite 処理は変更なし**
- ✅ **Docker なし環境でも動作**: ホスト側コマンド使用

## 実装計画

### Phase 1: DockerCommandExecutor 拡張
1. `exec_command()` メソッド実装
   - stdin サポート
   - stdout/stderr キャプチャ
   - エラーハンドリング

2. `is_container_running()` メソッド実装
   - get_container_status() を利用
   - "Up" で始まる場合は True

3. ユニットテスト作成
   - `test_docker_command_executor.py` 拡張
   - exec_command のモックテスト
   - is_container_running のテスト

### Phase 2: db_backup.py Docker 対応
1. `backup_postgresql_via_docker()` 実装
   - docker exec + pg_dump
   - gzip 圧縮
   - エラーハンドリング

2. 既存 `backup_postgresql()` を `backup_postgresql_via_host()` にリネーム

3. 新しい `backup_postgresql()` エントリーポイント実装
   - コンテナ起動確認
   - Docker/Host 自動切り替え
   - ログ出力

4. テスト
   - マニュアルテスト（Docker 起動/停止両方）
   - ユニットテスト（モック）

### Phase 3: db_restore.py Docker 対応
1. `restore_postgresql_via_docker()` 実装
   - gzip 解凍
   - docker exec -i + psql
   - エラーハンドリング

2. 既存 `restore_postgresql()` を `restore_postgresql_via_host()` にリネーム

3. 新しい `restore_postgresql()` エントリーポイント実装
   - コンテナ起動確認
   - Docker/Host 自動切り替え
   - ログ出力

4. テスト
   - マニュアルテスト（Docker 起動/停止両方）
   - ユニットテスト（モック）

### Phase 4: ドキュメント更新
1. README.md に推奨環境を追記
   - Docker Desktop インストール推奨
   - ホスト pg_dump はオプション

2. トラブルシューティング追加
   - コンテナ未起動時の動作
   - フォールバック動作の説明

## テスト計画

### ユニットテスト
- `test_docker_command_executor_extended.py`
  - exec_command() の正常系/異常系
  - is_container_running() のテスト
  - stdin 注入のテスト

- `test_db_backup_docker.py`
  - backup_postgresql_via_docker() のモックテスト
  - コンテナ起動/停止時の切り替えテスト
  - エラーケース（コンテナ不在、pg_dump 失敗など）

- `test_db_restore_docker.py`
  - restore_postgresql_via_docker() のモックテスト
  - コンテナ起動/停止時の切り替えテスト
  - エラーケース（コンテナ不在、psql 失敗など）

### マニュアルテスト
1. **Docker コンテナ起動時**:
   ```bash
   poetry run postgres_start
   poetry run db_backup
   # → Docker exec 経由で実行されることを確認
   
   poetry run db_restore
   # → Docker exec 経由で実行されることを確認
   ```

2. **Docker コンテナ停止時**:
   ```bash
   poetry run postgres_stop
   poetry run db_backup
   # → ホスト pg_dump にフォールバック（警告メッセージ表示）
   
   poetry run db_restore
   # → ホスト gunzip/psql にフォールバック（警告メッセージ表示）
   ```

3. **エラーケース**:
   - Docker Desktop 未起動
   - コンテナ存在しない
   - ホスト pg_dump も不在

## 期待される効果

### ユーザー体験の向上
- ❌ **Before**: PostgreSQL クライアントツールのインストール必須
- ✅ **After**: Docker Desktop だけで完結

### 実装例

**Before (Issue #048)**:
```bash
# Windows ユーザー
> poetry run db_backup
ERROR: pg_dump command not found. Please install PostgreSQL client tools.

# 手動で PostgreSQL クライアントをインストール...
# PATH 設定...
# バージョン確認...
```

**After (Issue #049)**:
```bash
# Docker コンテナ起動中
> poetry run db_backup
INFO: Using Docker container: repom_postgres
INFO: Backup created successfully: db_20260224_150000.sql.gz

# Docker コンテナ停止中
> poetry run db_backup
WARNING: Container repom_postgres not running, using host pg_dump
ERROR: pg_dump command not found. Please install PostgreSQL client tools.
# (フォールバックで既存動作を維持)
```

## 関連リソース

- **Issue #048**: PostgreSQL スクリプト対応（完了済み）
- **repom/postgres/manage.py**: Docker exec の既存実装例（Line 61）
- **repom/_.docker_manager.py**: Docker 管理基盤
- **repom/scripts/db_backup.py**: 現行実装
- **repom/scripts/db_restore.py**: 現行実装

## 備考

### Docker Desktop 必須化について
この変更により、PostgreSQL バックアップ・リストアの推奨環境は「Docker Desktop インストール済み」になります。

ただし、後方互換性は 100% 維持されます：
- ホスト pg_dump が利用可能な環境では引き続き動作
- Docker なし環境でも既存動作を維持

### パフォーマンス考慮
- Docker exec のオーバーヘッドは最小限（< 100ms）
- データ転送は stdout/stdin 経由で効率的
- gzip 圧縮はホスト側で実行（コンテナ外）

### セキュリティ
- PGPASSWORD 環境変数は docker exec に渡さない
- コンテナ内の認証は Docker network 経由
- バックアップファイルのパーミッションは変更なし
