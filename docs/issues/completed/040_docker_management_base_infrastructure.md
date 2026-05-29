# Issue #040: Docker 管理操作の統一基盤

**ステータス**: ✅ 完了（Phase 1-2 完了）

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

## 実装方針の確定

### アーキテクチャ

```
repom/_/docker_manager.py
  ├── DockerManager (ABC)
  ├── DockerCommandExecutor
  ├── ReadinessChecker
  └── ユーティリティ関数

利用側:
  repom/postgres/manage.py → PostgresManager (repom/_/docker_manager の利用)
  fast-domain/redis/manage.py → RedisManager (repom/_/docker_manager の利用)
```

**特性**:
- 基盤を `repom/_` 配下に配置（汎用・再利用可能）
- repom と fast-domain 両方で使用
- テスト戦略: 実 Docker で信頼性検証（mock なし）
- 既存コマンドインターフェース維持（互換性維持）
- Config-based design（repom + fast-domain 両対応）
- 互換性考慮なし（新規設計）

---

## 提案される解決策

### Phase 1: 共通基盤設計

repom に `repom/_/docker_manager.py` を作成し、以下の共通基盤を実装：

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
- `repom/_/docker_manager.py` - 共通基盤（約300-400行、単一ファイル）
- `docs/guides/features/docker_manager_guide.md` - 使用ガイド
- `docs/technical/docker_manager_architecture.md` - 設計ドキュメント

**修正**:
- `repom/postgres/manage.py` - DockerManager ベースに統合（100-150行削減）

**外部プロジェクト** (fast-domain など):
- `src/fast_domain/arq/scripts/redis/manage.py` - DockerManager ベースに統合（150-200行削減）

## 実装計画

### 第1段階: 基盤設計・実装（Phase 1）

**目標**: `repom/_/docker_manager.py` 完成 + テスト

1. DockerManager ABC + ユーティリティ実装
   - `DockerManager` 抽象基盤クラス
   - `DockerCommandExecutor` (docker-compose/docker 実行)
   - `ReadinessChecker` (readiness check 汎用)
   - ユーティリティ関数群
2. PostgresManager 参考実装
3. 単体テスト作成（15個程度）
4. ドキュメント作成

**期間**: 2-3日想定

### 第2段階: repom 統合（Phase 2）

**目標**: `repom/postgres/manage.py` 統合 + 互換性確認

1. PostgresManager を repom/postgres/manage.py に組み込み
2. 既存テスト全パス確認（互換性検証）
3. 統合テスト作成（5個程度）

**期間**: 1日想定

### 第3段階: 外部プロジェクト統合（Phase 3）

**対象**: fast-domain など

1. fast-domain (redis/manage.py) への適用
2. MongoDB など他サービスへの展開検証

**期間**: fast-domain 側で実施（後続タスク）

## テスト計画

### テスト戦略

**基本方針**: 実 Docker でテスト（Docker の操作信頼性を保証）
- mock なし → 実際の docker/docker-compose コマンドで検証
- 開発環境は SQLite で高速化（DB テストとは独立）
- CI/CD（GitHub Actions）で Docker が利用可能であることが前提

### 単体テスト

- `test_docker_command_executor.py` - docker-compose/docker コマンド実行
- `test_postgres_manager.py` - PostgreSQL 固有（generate 含む）
- `test_readiness_checker.py` - readiness check 汎用ロジック

### 統合テスト

- PostgreSQL フルライフサイクル（generate → start → stop → remove）
- Redis フルライフサイクル（start → stop → remove）
- エラーハンドリング（docker-compose 不在、コンテナ起動失敗など）
- 並行操作（複数サービス同時実行）

### 受け入れ基準

1. 既存機能がすべて動作（互換性テスト 100% パス）
2. コード行数削減
   - repom/postgres/manage.py: 355行 → 248行（-107, 30%）
3. 実 Docker テスト成功
   - Unit tests: 15+ 個
   - Integration tests: 5+ 個
   - 合計: 20+個テスト
4. ドキュメント整備完了
   - `docs/guides/features/docker_manager_guide.md`
   - `docs/technical/docker_manager_architecture.md`
   - コード内 docstring 充実

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
