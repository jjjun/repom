# Issue #041: Redis Docker 統合（repom）

**ステータス**: 🟢 計画中

**作成日**: 2026-02-23

**優先度**: 高

**関連Issue**: #040（Docker 管理基盤）の Phase 3 に相当

## 問題の説明

現在、db 関連の処理は以下のように分散している：
- **PostgreSQL**: repom で管理（`repom/postgres/manage.py`）
- **Redis**: 外部プロジェクト（fast-domain）で独立管理

この分散を解決し、**db 関連の処理をすべて repom で一元管理** したい。

## 目標

Redis Docker 環境の統一的な管理インターフェースを repom に構築し、以下を実現する：

```
repom/
├── postgres/          # ✅ PostgreSQL 管理（既存）
└── redis/             # ✨ **Redis 管理（新規）**
    ├── manage.py      # RedisManager クラス
    ├── docker-compose.template.yml
    └── init.template   # Redis 初期化設定
```

## 現状分析

### 分散状態の問題

1. **抽象度低下**: Redis を fast-domain が独立で管理
   - 将来的に他プロジェクトでも Redis が必要な場合、同じコード重複が発生
2. **共有困難**: Redis ベストプラクティスが repom に集約されない
3. **メンテナンス性**: PostgreSQL と Redis で異なるインターフェース

### Issue #040 との関係

- #040: **Docker 管理基盤**（`repom/_/docker_manager.py` ）を作成
- #041: **Redis を repom に統合**（#040 の基盤を使用）

```
#040 完成（Phase 1-2）
  ↓
DockerManager 基盤 + PostgresManager ✅
  ↓
#041 (Phase 3)
  ↓
RedisManager も repom に ← **本 Issue**
```

## 提案される解決策

### アーキテクチャ

```python
# repom/redis/manage.py

from repom._.docker_manager import DockerManager

class RedisManager(DockerManager):
    """Redis Docker コンテナ管理"""
    
    def __init__(self, config: RepomConfig):
        self.config = config
    
    def get_container_name(self) -> str:
        return "repom_redis"
    
    def get_compose_file_path(self) -> Path:
        return self.config.redis_compose_file
    
    def wait_for_service(self) -> None:
        """redis-cli ping で健全性確認"""
        pass
    
    # 以下は共通メソッド（DockerManager から継承）
    # start(), stop(), remove(), status(), is_running()
```

### ファイル構成

**新規作成**:
- `repom/redis/manage.py` - RedisManager クラス（~120行）
- `repom/redis/docker-compose.template.yml` - テンプレート
- `docs/guides/features/redis_manager_guide.md` - 使用ガイド
- `tests/unit_tests/test_redis_manager.py` - テスト（12-15個）

**修正**:
- `repom/config.py` - Redis 設定プロパティ追加
- `pyproject.toml` - Redis CLI スクリプト entry points 追加

### CLI コマンド

```bash
# Redis 環境生成
poetry run redis_generate

# Redis 起動
poetry run redis_start

# Redis 停止
poetry run redis_stop

# Redis 削除
poetry run redis_remove

# ステータス確認
poetry run redis_status
```

### 設定（RepomConfig）

```python
# repom/config.py

class RepomConfig:
    # ... PostgreSQL 設定 ...
    
    # 🆕 Redis 設定
    @property
    def redis_port(self) -> int:
        """Redis ポート（デフォルト: 6379）"""
        return int(getenv('REDIS_PORT', '6379'))
    
    @property
    def redis_compose_file(self) -> Path:
        """docker-compose ファイルパス"""
        return self.data_dir / 'docker-compose.generated.yml'
    
    @property
    def redis_enabled(self) -> bool:
        """Redis を有効にするか"""
        return getenv('REDIS_ENABLED', 'false').lower() == 'true'
```

### Docker Compose テンプレート

```yaml
# repom/redis/docker-compose.template.yml

version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: repom_redis
    ports:
      - "{{ redis_port }}:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    
  # オプション: RedisInsight（管理 UI）
  redisinsight:
    image: redislabs/redisinsight:latest
    container_name: repom_redisinsight
    ports:
      - "8001:8001"
    volumes:
      - redisinsight_data:/data
    depends_on:
      - redis

volumes:
  redis_data:
  redisinsight_data:
```

## 実装計画

### Phase 3: Redis 統合（⬅️ 本 Issue）

#### ステップ 1: RedisManager 実装（1-2時間）

```python
# repom/redis/manage.py

from pathlib import Path
from repom._.docker_manager import DockerManager
from repom.config import RepomConfig

class RedisManager(DockerManager):
    def __init__(self, config: RepomConfig):
        self.config = config
    
    def get_container_name(self) -> str:
        return "repom_redis"
    
    def get_compose_file_path(self) -> Path:
        return self.config.redis_compose_file
    
    def wait_for_service(self, max_retries: int = 30) -> None:
        """redis-cli ping で健全性確認"""
        # 実装内容は redis_testing_guide.md 参照
```

#### ステップ 2: Config 拡張（30分）

```python
# repom/config.py に以下を追加

@property
def redis_port(self) -> int:
    return int(getenv('REDIS_PORT', '6379'))

@property
def redis_compose_file(self) -> Path:
    return self.data_dir / 'docker-compose.generated.yml'
```

#### ステップ 3: docker-compose テンプレート作成（30分）

- `repom/redis/docker-compose.template.yml` 作成
- generate() 関数で yaml 生成
- PostgreSQL の generate() と同じパターンで実装

#### ステップ 4: CLI 統合（1時間）

```python
# pyproject.toml に追加

[tool.poetry.scripts]
redis_generate = "repom.redis.manage:generate"
redis_start = "repom.redis.manage:start"
redis_stop = "repom.redis.manage:stop"
redis_remove = "repom.redis.manage:remove"
```

#### ステップ 5: テスト実装（1-2時間）

- Unit test: 12-15個
- 内容: PostgreSQL Manager と同じパターン（wait_for_service, status など）
- 実 Redis コンテナで動作確認

```python
# tests/unit_tests/test_redis_manager.py

class TestRedisManager:
    def test_init(self, redis_manager):
        assert redis_manager.get_container_name() == "repom_redis"
    
    def test_wait_for_service_timeout(self, redis_manager):
        with pytest.raises(TimeoutError):
            redis_manager.wait_for_service(max_retries=2)
    
    # ... など 15個程度
```

#### ステップ 6: ドキュメント作成（1時間）

- `docs/guides/features/redis_manager_guide.md` - 使用ガイド
- コード内 docstring 充実
- CLI コマンドのヘルプ

### 実装期間

- **想定**: 3-4日
- 分解:
  - 基盤実装: 2-3日（4時間 × 3-4日）
  - テスト: 1-2日
  - ドキュメント: 1日

## 技術的検討

### Redis 設定の複数パターン

1. **基本的な Redis**（最小構成）
   ```yaml
   services:
     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"
   ```

2. **Redis + RedisInsight**（管理 UI 付き）
   ```yaml
   services:
     redis:
     redisinsight:  # ← 追加
   ```

3. **Redis Cluster**（将来対応）

→ 実装時に選択肢を提供

### 環境別構成

```bash
# .env
REDIS_ENABLED=true        # Redis 使用を有効化
REDIS_PORT=6379           # ポート指定
REDIS_SNAPSHOT_COUNT=100  # Snapshot 設定（オプション）
```

### SQL ベースの初期化との異なり

- PostgreSQL: `generate_init_sql()` で初期 DB 作成
- Redis: キーバリューストアなので初期化スクリプト不要（snapshot で管理）

```python
# redis/manage.py
def generate(self):
    """docker-compose.yml のみ生成"""
    # PostgreSQL の generate_init_sql() は不要
```

## 受け入れ基準

1. **RedisManager クラス完成**
   - ✅ `repom/redis/manage.py` 実装（~120行）
   - ✅ DockerManager を継承
   - ✅ all 5 abstract methods 実装

2. **CLI コマンド動作**
   - ✅ `poetry run redis_generate` で docker-compose.yml 生成
   - ✅ `poetry run redis_start` で Redis 起動
   - ✅ `poetry run redis_stop` で Redis 停止
   - ✅ `poetry run redis_remove` で Redis 削除

3. **テスト完備**
   - ✅ 12-15 個の unit test 実装
   - ✅ 実 Redis Docker で動作確認
   - ✅ 既存テスト 740 個すべてパス

4. **ドキュメント**
   - ✅ `docs/guides/features/redis_manager_guide.md`
   - ✅ Code docstring（クラス、メソッド）
   - ✅ CLI help との連携

5. **コード品質**
   - ✅ Type hints 完全実装
   - ✅ Error handling（TimeoutError, CalledProcessError など）
   - ✅ User messaging（🐳, ✅, ❌ 等）

## 影響範囲

### 新規作成ファイル

- `repom/redis/manage.py` (~120行)
- `repom/redis/docker-compose.template.yml` (~40行)
- `repom/redis/__init__.py`
- `tests/unit_tests/test_redis_manager.py` (~250行)
- `docs/guides/features/redis_manager_guide.md` (~150行)

### 既存修正ファイル

- `repom/config.py` - Redis 設定プロパティ追加（+20行）
- `pyproject.toml` - redis_* script entry points 追加（+5行）

### db 一元化の成果

```
修正前（分散）:
├── repom/postgres/manage.py         ✅
└── fast-domain/.../redis/manage.py  ❌

修正後（一元化）:
repom/
├── postgres/manage.py  ✅
└── redis/manage.py     ✅ ← 新規、repom に統合
```

## 重要ポイント

1. **#040 の基盤活用**
   - DockerManager, DockerCommandExecutor を活用
   - PostgresManager のパターンを踏襲

2. **既存との互換性維持**
   - PostgreSQL 機能 (generate_init_sql など) は変更なし
   - CRUD パターン同一（start/stop/remove）

3. **今後の拡張性**
   - MongoDB, Elasticsearch など他 db 追加が容易に
   - Template Method パターンで統一

4. **関連ドキュメント参照**
   - `docs/guides/tmp/redis_*.md` - fast-domain 向け資料は参考参考にしつつ、repom に最適化

## 関連資料

- **#040**: Docker 管理基盤（DockerManager, DockerCommandExecutor）
- **参考実装**: `repom/postgres/manage.py`
- **基盤クラス**: `repom/_/docker_manager.py`

## 次のアクション

- [ ] Issue #041 承認
- [ ] 実装開始
- [ ] テスト作成
- [ ] ドキュメント作成
- [ ] PR 作成 & レビュー

---

**作成者**: GitHub Copilot  
**最終更新**: 2026-02-23
