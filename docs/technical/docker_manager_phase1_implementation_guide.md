# Phase 1 実装設計書：Docker 管理基盤

**対象**: 当初は `repom/_/docker_manager.py` の実装。現行の汎用基盤は `basekit.docker_manager` に移管済み。
**目標**: 共通基盤完成 + PostgreSQL 参考実装 + テスト  
**期間**: 2-3日

---

## 📐 API 設計（確定版）

### 1. DockerManager (ABC)

```python
from abc import ABC, abstractmethod
from pathlib import Path

class DockerManager(ABC):
    """Docker コンテナ管理の基盤クラス
    
    サブクラスが実装すべきメソッド:
    - get_container_name()
    - get_compose_file_path()
    - wait_for_service()
    """
    
    @abstractmethod
    def get_container_name(self) -> str:
        """コンテナ名を返す
        
        Returns:
            コンテナの実行名（docker ps で見える名前）
        """
        pass
    
    @abstractmethod
    def get_compose_file_path(self) -> Path:
        """docker-compose ファイルのパスを返す
        
        Returns:
            ファイルが存在しない場合は FileNotFoundError を raise
        
        Raises:
            FileNotFoundError: compose ファイルが見つからない
        """
        pass
    
    @abstractmethod
    def wait_for_service(self, max_retries: int = 30) -> None:
        """サービス起動を待機（サービス固有の健全性確認）
        
        Args:
            max_retries: 最大リトライ回数（秒単位）
        
        Raises:
            TimeoutError: max_retries 秒以内に起動しなかった
        """
        pass
    
    # ===== 共通メソッド（DockerManager が実装）=====
    
    def start(self) -> None:
        """コンテナを起動
        
        処理流れ:
        1. get_compose_file_path() で file 確認
        2. docker-compose up -d 実行
        3. wait_for_service() で起動待機
        4. ユーザーメッセージ表示
        """
        pass
    
    def stop(self) -> None:
        """コンテナを停止（削除しない）
        
        処理流れ:
        1. get_compose_file_path() で file 確認
        2. docker-compose stop 実行
        3. ユーザーメッセージ表示
        """
        pass
    
    def remove(self) -> None:
        """コンテナとボリュームを削除
        
        処理流れ:
        1. get_compose_file_path() で file 確認
        2. docker-compose down -v 実行
        3. ユーザーメッセージ表示
        """
        pass
    
    def status(self) -> bool:
        """ステータス確認（実行中か）
        
        Returns:
            True = 実行中、False = 停止中
        """
        pass
    
    def is_running(self) -> bool:
        """実行中か確認（status() の alias）"""
        pass
```

---

### 2. DockerCommandExecutor（スタティック）

```python
import subprocess
from pathlib import Path
from typing import Callable

class DockerCommandExecutor:
    """docker/docker-compose コマンントの実行ユーティリティ
    
    全メソッドはスタティック（ステートレス）
    """
    
    @staticmethod
    def run_docker_compose(
        command: str,
        compose_file: Path,
        cwd: Path | None = None,
        capture_output: bool = False
    ) -> str | None:
        """docker-compose コマンドを実行
        
        Args:
            command: 実行コマンド（例: "up -d", "stop", "down -v"）
            compose_file: docker-compose.yml のパス
            cwd: 作業ディレクトリ（デフォルト: compose_file の親）
            capture_output: True なら stdout 返す
        
        Returns:
            capture_output=True の場合は stdout、否則 None
        
        Raises:
            subprocess.CalledProcessError: コマンド失敗
            FileNotFoundError: docker-compose コマンド不在
        """
        pass
    
    @staticmethod
    def get_container_status(container_name: str) -> str:
        """docker ps でコンテナのステータスを取得
        
        Args:
            container_name: コンテナ名
        
        Returns:
            ステータス文字列（例: "Up 10 minutes"）
            見つからない場合は空文字列
        
        Raises:
            FileNotFoundError: docker コマンド不在
        """
        pass
    
    @staticmethod
    def wait_for_readiness(
        check_func: Callable[[], bool],
        max_retries: int = 30,
        interval_sec: int = 1,
        service_name: str = "Service"
    ) -> None:
        """Readiness check（汎用ループ）
        
        Args:
            check_func: 健全性確認関数（True = 起動完了）
            max_retries: 最大リトライ回数（秒単位）
            interval_sec: リトライ間隔（秒）
            service_name: サービス名（メッセージ表示用）
        
        Raises:
            TimeoutError: max_retries 秒以内に起動しなかった
        """
        pass
```

---

### 3. ユーティリティ関数群

```python
def print_message(
    symbol: str,
    message: str,
    details: list[str] | None = None
) -> None:
    """ユーザーメッセージ表示
    
    Args:
        symbol: 絵文字（🐳, ✅, ❌ など）
        message: メインメッセージ
        details: 詳細情報（行頭スペース付き）
    
    Example:
        print_message("🐳", "Starting PostgreSQL container...")
        print_message("✅", "PostgreSQL is ready", [
            "Host: localhost",
            "Port: 5432"
        ])
    """
    pass


def validate_compose_file_exists(
    compose_file: Path,
    service_name: str
) -> None:
    """Compose ファイル存在チェック
    
    Args:
        compose_file: ファイルパス
        service_name: サービス名（エラーメッセージ用）
    
    Raises:
        FileNotFoundError: ファイルが見つからない
    """
    pass


def format_connection_info(
    host: str,
    port: int,
    **kwargs
) -> list[str]:
    """接続情報をフォーマット
    
    Returns:
        整形済みの情報行リスト
    
    Example:
        format_connection_info(
            host="localhost",
            port=5432,
            user="postgres",
            databases=["repom_dev", "repom_test", "repom_prod"]
        )
    """
    pass
```

---

## 🏗️ ファイル構成

### `basekit.docker_manager` 構成

```
1. Imports (5-10 行)
2. DockerCommandExecutor (100-120 行)
   - run_docker_compose()
   - get_container_status()
   - wait_for_readiness()
3. DockerManager ABC (80-100 行)
   - 抽象メソッド 3個
   - 共通メソッド 5個
4. ユーティリティ関数 (60-80 行)
   - print_message()
   - validate_compose_file_exists()
   - format_connection_info()
5. PostgresManager 参考実装 (60-80 行)
   - __init__, get_container_name, get_compose_file_path
   - wait_for_service, generate_docker_compose など
6. Docstrings / Comments (30-50 行)

合計: 約 330-400 行
```

---

## 🧪 テスト構成（Phase 1）

### テストファイル置き場

```
tests/unit_tests/
├── docker_manager/
│   ├── __init__.py
│   ├── test_docker_command_executor.py  (8 tests)
│   ├── test_docker_manager.py           (4 tests)
│   └── test_postgres_manager.py         (5 tests)
└── ...（既存）
```

### テストケース詳細（17個）

#### A. DockerCommandExecutor（8個）

```python
def test_run_docker_compose_success():
    """docker-compose コマンド成功"""
    # モック docker-compose で "up -d" 実行検証

def test_run_docker_compose_not_found():
    """docker-compose コマンド不在"""
    # FileNotFoundError をキャッチ

def test_run_docker_compose_failure():
    """docker-compose コマンド失敗"""
    # exit code != 0

def test_get_container_status_running():
    """コンテナ実行中"""
    # "Up 10 minutes" のような文字列を返す

def test_get_container_status_stopped():
    """コンテナ停止中"""
    # "Exited" または空文字列

def test_get_container_status_not_found():
    """コンテナが見つからない"""
    # 空文字列を返す

def test_wait_for_readiness_success():
    """Readiness check 成功（即座）"""
    # check_func が True をすぐ返す

def test_wait_for_readiness_timeout():
    """Readiness check タイムアウト"""
    # max_retries=3 で 3秒以上待機時 TimeoutError
```

#### B. DockerManager ABC（4個）

```python
def test_postgres_manager_instantiation():
    """PostgresManager インスタンス作成"""

def test_docker_manager_start():
    """start() の実行フロー"""
    # get_compose_file_path + wait_for_readiness が呼ばれる

def test_docker_manager_stop():
    """stop() の実行フロー"""

def test_docker_manager_remove():
    """remove() の実行フロー"""
```

#### C. PostgresManager（5個）

```python
def test_postgres_manager_wait_for_postgres():
    """pg_isready による待機"""

def test_postgres_manager_get_container_name():
    """コンテナ名取得"""

def test_postgres_manager_get_compose_file_path():
    """compose ファイルパス取得"""

def test_postgres_manager_full_lifecycle():
    """フルライフサイクル: generate → start → stop → remove"""

def test_postgres_manager_error_handling():
    """エラーハンドリング（docker 不在など）"""
```

---

## 🔧 実装手順

### ステップ 1: 基本クラス実装（60 分）

```python
# 1. DockerCommandExecutor スケルトン
#    - subprocess.run の基本ラッパー
#    - 例外ハンドリング基本形

# 2. DockerManager ABC スケルトン
#    - 抽象メソッド定義
#    - 共通 start/stop/remove 実装（骨組み）

# 3. ユーティリティ関数
#    - print_message()
#    - validate_compose_file_exists()
```

### ステップ 2: PostgresManager 実装（90 分）

```python
# 1. PostgresManager クラス作成
# 2. 抽象メソッド実装
# 3. wait_for_service() に pg_isready 組み込み
# 4. config 対応
```

### ステップ 3: テスト作成（120 分）

```python
# Phase 1a: Unit tests（8-10個）
#   - 基本機能確認
#   - 例外ハンドリング

# Phase 1b: Integration tests（7-9個）
#   - 実 Docker コンテナ操作
#   - ライフサイクル全体
```

### ステップ 4: ドキュメント（60 分）

```python
# 1. docs/guides/features/docker_manager_guide.md
#    - 使用例
#    - API リファレンス

# 2. docs/technical/docker_manager_phase1_implementation_guide.md
#    - 設計思想
#    - 拡張方法（MongoManager など）

# 3. Docstring 充実
```

---

## 📌 実装上の注意点

### 1. Config 統合

```python
# PostgresManager は config から以下を取得:
- config.postgres.container.get_container_name()
- config.postgres.container.host_port
- config.postgres.user
- config.postgres.password
- config.postgres.database
- config.pgadmin.container.enabled
```

### 2. エラーメッセージの統一

```
🐳 Starting PostgreSQL container...
⏳ Waiting for PostgreSQL to be ready...
✅ PostgreSQL is ready
❌ Failed to start PostgreSQL: [error]
⚠️  docker-compose.generated.yml が見つかりません
```

### 3. Readiness Check の精度

```python
# PostgreSQL の場合:
for i in range(max_retries):
    docker exec <container> pg_isready -U <user>
    if returncode == 0: return  ← 起動完了
    
    if (i + 1) % 5 == 0: print(...)  ← 5秒ごと進捗表示
    time.sleep(1)

# 合計待機時間: max_retries 秒（デフォルト 30秒）
```

### 4. テストでの Docker 要件

```
GitHub Actions 環境で Docker が使える想定
- ubuntu-latest には Docker/Docker Desktop 込み
- ローカルテストも Docker Desktop 稼働時前提
```

---

## ✅ 完了条件（Phase 1）

- [x] 汎用基盤を `basekit.docker_manager` として実装済み
- [ ] Unit tests 15+ 個パス
- [ ] PostgreSQL 既存機能全て動作確認
- [ ] ドキュメント完成
- [ ] git commit "feat(docker_manager): Implement Docker management base infrastructure"

---

**作成日**: 2026-02-23  
**対象バージョン**: repom v0.1.0  
**次ステップ**: 実装開始 → Phase 2（repom 統合）
