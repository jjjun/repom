# Issue #040: Docker 管理操作の統一基盤

**ステータス**: 🟡 提案中

**作成日**: 2026-02-23

**優先度**: 中

## 問題の説明

現在、repom（PostgreSQL）と fast-domain（Redis）には、Docker コンテナの管理スクリプト（manage.py）が独立して存在しており、以下の問題がある：

1. **コード重複**: docker-compose ファイル操作、readiness check、ステータス確認など、類似パターンが両プロジェクトに存在
2. **保守性低下**: バグ修正や機能追加時に両ファイルを修正する必要がある
3. **一貫性欠如**: エラーハンドリング、出力フォーマット、コマンドインターフェースが微妙に異なる
4. **知見の局所化**: 一方での改善が他方に反映されていない

## 現状分析

### fast-domain Redis manage.py

**位置**: `fast-domain/src/fast_domain/arq/scripts/redis/manage.py`

**実装機能**:
- `start()` - docker-compose up + readiness wait
- `stop()` - docker-compose stop（コンテナ停止のみ）
- `remove()` - docker-compose down（コンテナ削除）
- `status()` - コンテナステータス確認 + ping チェック
- `wait_for_redis()` - redis-cli ping による健全性確認
- `_get_container_status()` - docker ps コマンドでステータス取得
- `_ping_redis()` - docker exec redis-cli ping

**特性**:
- Static docker-compose.yml を使用（ファイルシステム参照）
- 単一サービス（Redis のみ）
- シンプルなコマンドラインインターフェース
- 進捗表示、エラーハンドリングが充実

### repom PostgreSQL manage.py

**位置**: `repom/postgres/manage.py`

**実装機能**:
- `generate()` - docker-compose.yml を動的生成
- `start()` - docker-compose up + readiness wait
- `stop()` - docker-compose down（現状、削除を行っている）
- `wait_for_postgres()` - pg_isready による健全性確認
- `generate_docker_compose()` - DockerComposeGenerator で yaml を生成
- `generate_init_sql()` - 環境別DB作成スクリプル生成
- `generate_pgadmin_servers_json()` - pgAdmin 設定ファイル生成

**特性**:
- `repom/_.docker_compose.py` で汎用 DockerComposeGenerator を実装
- 複数サービス対応（PostgreSQL + pgAdmin オプション）
- 動的な設定生成
- config オブジェクトによるカスタマイズ対応

## 共通パターン抽出

### 1. Docker Compose 操作（レベル1 - 基本）

```
共通: docker-compose コマンド実行
  - up -d（起動）
  - stop（停止）
  - down（削除）

相違:
  - Redis: ファイルシステムから compose ファイル参照
  - PostgreSQL: 動的生成した compose ファイル参照
```

### 2. Readiness Check パターン

```
共通: サービス起動を待機
  - リトライループ（最大30秒）
  - 5秒ごとの進捗表示
  - タイムアウト時に例外

実装詳細:
  - Redis: redis-cli ping
  - PostgreSQL: pg_isready
```

### 3. コンテナステータス確認

```
共通: docker ps でステータス取得
  - コンテナ名でフィルタリング
  - ステータス文字列解析
```

### 4. エラーハンドリング

```
共通: 標準的な例外処理
  - FileNotFoundError（docker command不在）
  - CalledProcessError（コマンド失敗）
  - TimeoutError（起動失敗）
```

### 5. ユーザーメッセージング

```
共通: 絵文字を使った進捗表示
  - 🐳 起動中
  - 🛑 停止中
  - ✅ 成功
  - ❌ 失敗
```

## 提案される解決策

### Phase 1: 共通基盤設計

repom に `repom/docker_manager.py` を作成し、以下の共通基盤を実装：

```python
class DockerManager(ABC):
    """Docker コンテナ管理の基盤クラス"""
    
    @abstractmethod
    def get_container_name(self) -> str:
        """コンテナ名を取得"""
        pass
    
    @abstractmethod
    def get_compose_file_path(self) -> Path:
        """docker-compose ファイルのパスを取得"""
        pass
    
    @abstractmethod
    def wait_for_service(self, max_retries: int = 30) -> None:
        """サービスの起動を待機（サービス固有の実装）"""
        pass
    
    # 共通メソッド
    def start(self) -> None:
        """コンテナを起動"""
        
    def stop(self) -> None:
        """コンテナを停止"""
        
    def remove(self) -> None:
        """コンテナを削除"""
        
    def status(self) -> bool:
        """ステータス確認"""
        
    def is_running(self) -> bool:
        """実行中か確認"""
```

### Phase 2: 既存実装の抽出

#### DockerCommandExecutor（共通ユーティリティ）

```python
class DockerCommandExecutor:
    """Docker/docker-compose コマンド実行の共通ユーティリティ"""
    
    @staticmethod
    def run_docker_compose(
        command: str,
        compose_file: Path,
        cwd: Path | None = None
    ) -> None:
        """docker-compose コマンドを実行"""
        
    @staticmethod
    def get_container_status(container_name: str) -> str:
        """docker ps でステータス取得"""
        
    @staticmethod
    def wait_for_readiness(
        check_func: Callable[[], bool],
        max_retries: int = 30,
        interval_sec: int = 1
    ) -> None:
        """Readiness check（汎用）"""
```

#### サービス固有実装

```python
class PostgresManager(DockerManager):
    """PostgreSQL 専用"""
    
    def __init__(self, config: RepomConfig):
        self.config = config
    
    def wait_for_service(self) -> None:
        """pg_isready で待機"""
        
class RedisManager(DockerManager):
    """Redis 専用"""
    
    def wait_for_service(self) -> None:
        """redis-cli ping で待機"""
```

### Phase 3: 統合

#### fast-domain への適用

```python
# fast-domain/src/fast_domain/arq/scripts/redis/manage.py
from repom.docker_manager import DockerManager, DockerCommandExecutor

class RedisManager(DockerManager):
    def __init__(self, compose_dir: Path):
        self.compose_dir = compose_dir
        
    # 実装削減、基盤クラスの共通メソッドを利用
```

#### repom への既存コード更新

```python
# repom/postgres/manage.py
from repom.docker_manager import DockerManager

class PostgresManager(DockerManager):
    def __init__(self, config: RepomConfig):
        self.config = config
    
    # 既存機能は部分的に削減
```

## 影響範囲

### ファイル（新規作成/修正）

**新規** : 
- `repom/docker_manager.py` - 共通基盤（500-700行）
- `repom/docker_manager/` - サブモジュール化（オプション）
- `docs/guides/features/docker_manager_guide.md` - 使用ガイド

**修正**:
- `repom/postgres/manage.py` - 共通基盤を利用（100-150行削減）
- `repom/scripts/alembic_reset.py` - docker-compose 操作を更新（必要に応じて）
- `pyproject.toml` - 新しい entry points（postgres_reset など）

**外部プロジェクト** (fast-domain など):
- `src/fast_domain/arq/scripts/redis/manage.py` - 共通基盤適用（150-200行削減）

## 実装計画

### 第1段階: 基盤設計・実装

1. `DockerManager` 抽象基盤クラス設計
2. `DockerCommandExecutor` ユーティリティ実装
3. 単体テスト作成（15-20テスト）

### 第2段階: repom 統合

1. PostgresManager を基盤に移行
2. 既存 manage.py コードを削減
3. 互換性テスト（既存テスト全パス確認）

### 第3段階: 外部プロジェクト統合（フェーズ6）

1. fast-domain での試験運用
2. 共通パターン確認
3. MongoDB など他のサービスへの展開可能性検証

## テスト計画

### 単体テスト

- `test_docker_command_executor.py` - docker-compose コマンド実行
- `test_postgres_manager.py` - PostgreSQL 固有
- `test_redis_manager.py` - Redis 固有（fast-domain と共有）

### 統合テスト

- docker-compose のモック対応
- readiness check の各パターン
- エラーケース（docker 不在、コンテナ起動失敗など）

### 受け入れ基準

1. 既存機能がすべて動作
2. コード行数削減（repom: 150行以上、fast-domain: 200行以上）
3. 新規テスト: 20+個追加
4. ドキュメント整備完了

## 関連資料

### 参考実装

- `repom/_.docker_compose.py` - 汎用 docker-compose 生成基盤（再利用可能）
- `fast-domain/src/fast_domain/arq/scripts/redis/manage.py` - Redis 実装
- `repom/postgres/manage.py` - PostgreSQL 実装

### Issue リンク

- 関連: #038 (PostgreSQL コンテナ設定の カスタマイズ対応)

## 次のアクション

- [ ] Phase 1 設計承認
- [ ] 基盤クラス実装開始
- [ ] 単体テスト作成
- [ ] fast-domain との連携検討

---

**作成者**: GitHub Copilot  
**最終更新**: 2026-02-23
