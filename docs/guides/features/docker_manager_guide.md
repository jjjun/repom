# Docker Manager ガイド

**対象**: リポジトリのシステムを理解し、容器管理を実装する開発者  
**作成日**: 2026-02-23

---

## 📚 目次

1. [概要](#概要)
2. [基本的な使い方](#基本的な使い方)
3. [API リファレンス](#apiリファレンス)
4. [サービス固有の実装](#サービス固有の実装)
5. [エラーハンドリング](#エラーハンドリング)
6. [実装例](#実装例)

---

## 概要

Docker Manager は **複数のコンテナサービスを統一的に管理する基盤** を提供します。

### 特徴

- ✅ **共通基盤**: PostgreSQL、Redis、MongoDB など複数サービスに対応
- ✅ **テンプレートメソッドパターン**: 共通処理 + サービス特有処理の分離
- ✅ **エラーハンドリング**: Docker 不在、ファイル見つからず、タイムアウトなど
- ✅ **堅牢な待機ロジック**: Readiness check による確実な起動確認

### アーキテクチャ

```
DockerManager (ABC)
├── start()          ← テンプレートメソッド（共通）
├── stop()           ← テンプレートメソッド（共通）
├── remove()         ← テンプレートメソッド（共通）
├── status()         ← 共通実装（ステータス確認）
├── is_running()     ← 共通実装（status() の alias）
│
├── [抽象メソッド]
├── get_container_name()              ← サブクラスが実装
├── get_compose_file_path()           ← サブクラスが実装
└── wait_for_service()                ← サブクラスが実装（サービス固有）
```

---

## 基本的な使い方

### 1. 独自の Manager クラスを定義

```python
from pathlib import Path
from repom._ import docker_manager as dm


class MyServiceManager(dm.DockerManager):
    """My service のコンテナ管理"""
    
    def __init__(self, compose_dir: Path):
        self.compose_dir = compose_dir
    
    def get_container_name(self) -> str:
        """コンテナ名を返す"""
        return "my_service"
    
    def get_compose_file_path(self) -> Path:
        """docker-compose.yml のパスを返す"""
        compose_file = self.compose_dir / "docker-compose.yml"
        if not compose_file.exists():
            raise FileNotFoundError(f"Compose file not found: {compose_file}")
        return compose_file
    
    def wait_for_service(self, max_retries: int = 30) -> None:
        """サービスの起動を待機（サービス固有の健全性確認）"""
        def check_service_ready():
            try:
                # 例: my_service の API にアクセス
                result = subprocess.run(
                    ["curl", "-f", "http://localhost:8000/health"],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
                return result.returncode == 0
            except Exception:
                return False
        
        dm.DockerCommandExecutor.wait_for_readiness(
            check_service_ready,
            max_retries=max_retries,
            service_name="My Service"
        )
```

### 2. コンテナを操作

```python
from pathlib import Path
from my_app.services import MyServiceManager

# 初期化
compose_dir = Path.cwd() / "infrastructure"
manager = MyServiceManager(compose_dir)

# 起動
manager.start()
# 出力:
# 🐳 Starting my_service container...
# ⏳ Waiting for service to be ready...
# ✅ My Service is ready

# 状態確認
if manager.is_running():
    print("Running")
else:
    print("Stopped")

# 停止
manager.stop()
# 出力:
# 🛑 Stopping my_service container...
# ✅ my_service stopped

# 削除（ボリュームも含む）
manager.remove()
# 出力:
# 🧹 Removing my_service container and volumes...
# ✅ my_service removed
```

---

## API リファレンス

### DockerManager

#### `start()` → None

コンテナを起動します。

**処理フロー**:
1. compose ファイルの存在確認
2. `docker-compose up -d` を実行
3. `wait_for_service()` で起動待機
4. ユーザーメッセージ表示

**例外**:
- `FileNotFoundError`: compose ファイルが見つからない
- `subprocess.CalledProcessError`: docker-compose 失敗
- `TimeoutError`: サービスが起動しない（max_retries 秒以上待機）

---

#### `stop()` → None

コンテナを停止します（削除しない）。

**処理**:
1. compose ファイルの存在確認
2. `docker-compose stop` を実行
3. ユーザーメッセージ表示

**例外**:
- `FileNotFoundError`: compose ファイルが見つからない
- `subprocess.CalledProcessError`: docker-compose 失敗

---

#### `remove()` → None

コンテナとボリュームを削除します。

**処理**:
1. compose ファイルの存在確認
2. `docker-compose down -v` を実行
3. ユーザーメッセージ表示

**例外**:
- `FileNotFoundError`: compose ファイルが見つからない
- `subprocess.CalledProcessError`: docker-compose 失敗

---

#### `status()` → bool

コンテナが実行中かを確認します。

**返り値**:
- `True`: 実行中
- `False`: 停止中

**実装**:
```python
status = manager.status()
print("Running" if status else "Stopped")
```

---

#### `is_running()` → bool

`status()` の alias です（同じ機能）。

```python
# status() と is_running() は同じ
assert manager.status() == manager.is_running()
```

---

### DockerManager (抽象メソッド)

サブクラスは以下を実装する必要があります。

#### `get_container_name()` → str

**実装例**:
```python
def get_container_name(self) -> str:
    return "my_service"
```

---

#### `get_compose_file_path()` → Path

**実装例**:
```python
def get_compose_file_path(self) -> Path:
    compose_file = self.compose_dir / "docker-compose.yml"
    if not compose_file.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_file}")
    return compose_file
```

---

#### `wait_for_service(max_retries: int = 30)` → None

**実装例** (PostgreSQL の場合):
```python
def wait_for_service(self, max_retries: int = 30) -> None:
    def check_postgres_ready():
        try:
            result = subprocess.run(
                ["docker", "exec", self.get_container_name(), 
                 "pg_isready", "-U", "postgres"],
                capture_output=True,
                timeout=2,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    dm.DockerCommandExecutor.wait_for_readiness(
        check_postgres_ready,
        max_retries=max_retries,
        service_name="PostgreSQL"
    )
```

---

### DockerCommandExecutor

クラスメソッドのみ（ステートレス）。

#### `run_docker_compose(command, compose_file, cwd=None, capture_output=False)` → str | None

docker-compose コマンドを実行します。

**パラメータ**:
- `command`: 実行コマンド（例: `"up -d"`、`"stop"`）
- `compose_file`: docker-compose.yml のパス
- `cwd`: 作業ディレクトリ（デフォルト: compose_file の親）
- `capture_output`: True なら stdout を返す

**返り値**:
- `capture_output=True`: stdout 文字列
- `capture_output=False`: None

**例外**:
- `subprocess.CalledProcessError`: コマンド失敗
- `FileNotFoundError`: docker-compose コマンド不在

---

#### `get_container_status(container_name)` → str

コンテナの状態を取得します。

**返り値**:
- `"Up X minutes"` など: 実行中
- `"Exited"` など: 停止中
- `""` (空文字列): 見つからない

---

#### `wait_for_readiness(check_func, max_retries=30, interval_sec=1, service_name="Service")`

汎用の readiness check ループです。

**パラメータ**:
- `check_func`: 健全性確認関数（True = 起動完了）
- `max_retries`: 最大リトライ秒数
- `interval_sec`: リトライ間隔（秒）
- `service_name`: サービス名（メッセージ表示用）

**例外**:
- `TimeoutError`: max_retries 秒以内に起動しなかった

---

## サービス固有の実装

### PostgreSQL の例

[repom/postgres/manage.py](../../repom/postgres/manage.py) の `PostgresManager` を参照してください。

```python
from repom import BaseRepository
from repom.models import BaseModel

class PostgresManager(DockerManager):
    def __init__(self, config: RepomConfig):
        self.config = config
    
    def get_container_name(self) -> str:
        return f"repom_{self.config.postgres.container_name}"
    
    # ... (省略)
```

**設定の取得元**: `repom.config.RepomConfig`

### Redis の例（fast-domain）

外部プロジェクト（fast-domain）で `RedisManager` を定義します。

```python
# fast-domain/src/fast_domain/docker/redis_manager.py
from repom._ import docker_manager as dm

class RedisManager(dm.DockerManager):
    def __init__(self, compose_dir: Path):
        self.compose_dir = compose_dir
    
    def get_container_name(self) -> str:
        return "fast_domain_redis"
    
    # ... (省略)
```

---

## エラーハンドリング

### 1. Docker 未インストール

**エラー**: `FileNotFoundError: docker-compose command not found`

**対応**:
```python
try:
    manager.start()
except FileNotFoundError:
    print("❌ Docker Desktop がインストールされていません")
    print("   https://www.docker.com/products/docker-desktop/")
    sys.exit(1)
```

### 2. Compose ファイル を見つからない

**エラー**: `FileNotFoundError: Compose file not found: .../docker-compose.yml`

**対応**:
```
ヒント: 先に 'uv run postgres_generate' を実行してください
```

### 3. サービス起動タイムアウト

**エラー**: `TimeoutError: PostgreSQL did not start within 30 seconds`

**対応**:
- ローカル環境の性能確認（CPU/メモリ）
- Docker イメージのプル状況確認
- ログ確認: `docker logs <container_name>`

---

## 実装例

### Full Lifecycle (生成 → 起動 → 停止 → 削除)

```python
from pathlib import Path
from repom.config import RepomConfig
from repom.postgres.manage import PostgresManager

# 設定を読み込み
config = RepomConfig()

# Manager を初期化
manager = PostgresManager(config)

try:
    # 1. Docker image をビルド（PostgreSQL の場合）
    # manager.generate()  # TODO: Phase 2 で実装
    
    # 2. コンテナを起動
    print("📦 Starting PostgreSQL...")
    manager.start()
    
    # 3. 状態確認
    if manager.is_running():
        print("✅ PostgreSQL is ready")
        
        # ... アプリケーション処理 ...
    
    # 4. 停止
    print("⏹ Stopping PostgreSQL...")
    manager.stop()
    
except SystemExit as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

finally:
    # 5. クリーンアップ（オプション）
    # manager.remove()
    pass
```

### CLI からの使用

```bash
# 起動
uv run postgres_start

# 停止
uv run postgres_stop

# 削除
uv run postgres_remove

# ステータス確認
uv run postgres_status
```

---

## FAQ

**Q: `wait_for_service()` の `max_retries` はどの程度が妥当？**

A: デフォルトは 30 秒で、ほとんどのサービスに十分です。
- 高速 PC: 5-10 秒
- 通常 PC: 20-30 秒
- 遅い PC / CI: 60 秒

**Q: 複数のサービスを同時に管理できる？**

A: 現在のコードは 1 service ず 1 manager です。
将来の拡張:
```python
class ServiceGroup:
    def add_service(self, name, manager):
        ...
    
    def start_all(self):
        ...
```

**Q: Docker Compose ファイルのカスタマイズは？**

A: `get_compose_file_path()` では任意のパスを返せます。

```python
def get_compose_file_path(self) -> Path:
    env = os.getenv("COMPOSE_ENV", "dev")
    return self.compose_dir / f"docker-compose.{env}.yml"
```

---

## 関連ドキュメント

- [Docker Manager アーキテクチャ設計](../technical/docker_manager_architecture.md)
- [Docker Manager Phase 1 実装設計書](../technical/docker_manager_phase1_implementation_guide.md)
- [コード削減分析](../technical/docker_manager_code_reduction_analysis.md)

---

**最終更新**: 2026-02-23
