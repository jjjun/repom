# Issue #042: Redis 設定管理と repom_info 統合

**ステータス**: ✅ 完了

**作成日**: 2026-02-23
**完了日**: 2026-02-23

**優先度**: 中

**関連Issue**: #041（Redis Docker 統合）

## 問題の説明

現在、Redis の統合は Issue #041 で完了していますが、以下の課題が残されています：

### 1. Redis 設定管理の不完全性

**現状**:
- `config.redis_port` のみ環境変数から取得
- `RedisConfig` クラスが存在しない（PostgreSQL の `PostgresConfig` と異なる）
- Redis コンテナ名（`repom_redis`）が `redis/manage.py` にハードコード
- Volume 名（`repom_redis_data`）も同様にハードコード

**期待動作**:
- PostgreSQL と同様に、`RedisConfig` + `RedisContainerConfig` クラスを実装
- ポート番号、コンテナ名、volume 名などを config で一元管理
- カスタマイズ可能にする

### 2. repom_info.py に Redis コネクション確認機能がない

**現状**:
- PostgreSQL コネクション確認: `test_postgres_connection()` ✅
- Redis コネクション確認: 未実装 ❌

**期待動作**:
```
[Redis Connection Test]
  Status            : ✓ Connected
```

のように Redis の接続可能性を確認表示する

## 期待される出力例（実装後）

```
[Redis Configuration]
  Host              : localhost
  Port              : 6379
  Container Name    : repom_redis
  Image             : redis:7-alpine

[Redis Connection Test]
  Status            : ✓ Connected

[Loaded Models] (N models found)
  ...
```

## 解決策

### Phase 1: Config に Redis 設定クラスを追加

**修正対象**: `repom/config.py`

PostgreSQL と同じパターンで実装（PostgresConfig に倣う構造）。

以下のクラスを追加予定：

```python
@dataclass
class RedisContainerConfig:
    """Redis Docker コンテナ設定（PostgresContainerConfig と同じパターン）
    
    Attributes:
        container_name: コンテナ名（None の場合は repom_redis）
        host_port: ホスト側のポート番号（デフォルト: 6379）
        volume_name: Volume名（None の場合は repom_redis_data）
        image: Redis イメージ（デフォルト: redis:7-alpine）
    """
    container_name: Optional[str] = field(default=None)
    host_port: int = field(default=6379)
    volume_name: Optional[str] = field(default=None)
    image: str = field(default="redis:7-alpine")

    def get_container_name(self) -> str:
        """コンテナ名を取得（デフォルト: repom_redis）"""
        return self.container_name or "repom_redis"

    def get_volume_name(self) -> str:
        """Volume名を取得（デフォルト: repom_redis_data）"""
        return self.volume_name or "repom_redis_data"


@dataclass
class RedisConfig:
    """Redis 設定（PostgresConfig と同じパターン）
    
    Attributes:
        host: Redis ホスト名（デフォルト: localhost）
        port: Redis ポート番号（デフォルト: 6379）
        password: Redis パスワード（オプション）
        database: Redis データベース番号（デフォルト: 0）
        container: Docker コンテナ設定
    
    環境変数ルール (PostgreSQL パターンを参考):
        - CONFIG_HOOK で config をカスタマイズ
        - または個別に環境変数から読み込み
    """
    host: str = field(default='localhost')
    port: int = field(default=6379)
    password: Optional[str] = field(default=None)
    database: int = field(default=0)
    container: RedisContainerConfig = field(default_factory=RedisContainerConfig)
```

**修正内容**:
1. `repom/config.py` に `RedisContainerConfig` クラスを追加
2. `RedisConfig` クラスを追加
3. `RepomConfig` に `redis: RedisConfig = field(default_factory=RedisConfig)` を追加

### Phase 2: repom_info.py に Redis コネクション確認機能を追加

**修正対象**: `repom/scripts/repom_info.py`

1. Redis テスト関数を追加（`redis-py` ライブラリを使用）:
```python
def test_redis_connection() -> str:
    """Test Redis connection using redis-py library
    
    Returns:
        Connection status message
        - "✓ Connected": Successfully connected
        - "⚠ redis-py not installed": redis library not available
        - "✗ Connection refused": Redis server not responding
        - "✗ Error: ...": Other connection errors
    """
    try:
        import redis
        
        r = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            socket_connect_timeout=2,
            socket_keepalive=True,
            health_check_interval=1
        )
        r.ping()  # PING コマンド実行
        return "✓ Connected"
        
    except ImportError:
        return "⚠ redis-py not installed"
    except redis.ConnectionError:
        return "✗ Connection refused"
    except Exception as e:
        return f"✗ Error: {type(e).__name__}"
```

2. `display_config()` に Redis 情報出力を追加:
```python
# [Redis Configuration] セクション
print("[Redis Configuration]")
print(f"  Host              : {config.redis.host}")
print(f"  Port              : {config.redis.port}")
print(f"  Container Name    : {config.redis.container.get_container_name()}")
print(f"  Image             : {config.redis.container.image}")
print()

# [Redis Connection Test] セクション
print("[Redis Connection Test]")
connection_status = test_redis_connection()
print(f"  Status            : {connection_status}")
print()
```

### Phase 3: redis/manage.py を config と統合

**修正対象**: `repom/redis/manage.py` (242行)

**現在のハードコード箇所**:
- **Line 41**: `get_container_name()` → `return "repom_redis"` にハードコード
- **Line 128-129**: `generate_docker_compose()` 内で `container_name = "repom_redis"`, `volume_name = "repom_redis_data"`
- **Line 142**: `image="redis:7-alpine"` 固定
- **Line 191-192**: `generate()` 出力で `"repom_redis"`, `"repom_redis_data"` ハードコード

**修正方針** (PostgreSQL の `postgres/manage.py` パターンに倣う):

```python
class RedisManager(dm.DockerManager):
    def __init__(self):
        self.config = config

    def get_container_name(self) -> str:
        """Redis コンテナ名を返す（config から取得）"""
        return self.config.redis.container.get_container_name()

    # 他のメソッド...


def generate_docker_compose() -> DockerComposeGenerator:
    """config から docker-compose.yml 生成器を作成"""
    redis_config = config.redis
    container_config = redis_config.container
    
    redis_service = DockerService(
        name="redis",
        image=container_config.image,
        container_name=container_config.get_container_name(),
        ports=[f"{redis_config.port}:6379"],
        volumes=[
            f"{container_config.get_volume_name()}:/data",
            ...
        ],
        ...
    )

def generate():
    """docker-compose.yml と Redis 設定を生成"""
    # ...
    print(f"   Container: {config.redis.container.get_container_name()}")
    print(f"   Volume: {config.redis.container.get_volume_name()}")
```

## 影響範囲

### 修正ファイル:
- `repom/config.py` -新クラス追加 + 構造変更
- `repom/scripts/repom_info.py` - Redis テスト機能追加
- `repom/redis/manage.py` - config 統合

### テスト追加:
- `tests/unit_tests/test_config_redis.py` - RedisConfig & RedisContainerConfig テスト（Phase 1-T）
- `tests/unit_tests/test_repom_info_redis.py` - repom_info Redis テスト（Phase 2-T）
- `tests/unit_tests/test_redis_manage.py` - redis/manage.py config 統合テスト（Phase 3-T）
- `tests/integration_tests/test_redis_docker.py` - 実コンテナでの統合テスト（Phase 4-3, オプション）

## 実装計画

### Phase 0: 依存関係設定

1. **Phase 0-1**: `pyproject.toml` に `redis` をオプション依存として追加
   ```toml
   [tool.poetry.extras]
   redis = ["redis>=5.0"]
   ```

### Phase 1: Config に Redis 設定クラスを追加

1. **Phase 1-1**: `repom/config.py` に `RedisContainerConfig` クラスを追加
2. **Phase 1-2**: `repom/config.py` に `RedisConfig` クラスを追加
3. **Phase 1-3**: `RepomConfig` に `redis: RedisConfig = field(default_factory=RedisConfig)` を追加
4. **Phase 1-T**: ✅ **テスト追加**: `tests/unit_tests/test_config_redis.py` を実装

### Phase 2: repom_info.py に Redis コネクション確認機能を追加

1. **Phase 2-1**: `test_redis_connection()` 関数を `repom_info.py` に追加（redis-py 使用）
2. **Phase 2-2**: `display_config()` に Redis セクションを追加
3. **Phase 2-T**: ✅ **テスト追加**: `tests/unit_tests/test_repom_info_redis.py` を実装

### Phase 3: redis/manage.py を config と統合

1. **Phase 3-1**: `redis/manage.py` を修正（config から値を取得）
2. **Phase 3-2**: ハードコード値をすべて config に置き換え
3. **Phase 3-T**: ✅ **テスト追加**: `tests/unit_tests/test_redis_manage.py` を実装

### Phase 4: その他のテスト・検証（オプション）

1. **Phase 4-1**: CONFIG_HOOK テスト実装
2. **Phase 4-2**: 統合テスト実装（`tests/integration_tests/test_redis_docker.py`）

## テスト戦略と実装計画

### 🔴 必須テスト

#### 1. `tests/unit_tests/test_config_redis.py` （PostgreSQL パターンに倣う）

```python
class TestRedisProperties:
    """RedisConfig のプロパティテスト"""
    
    def test_redis_host_default(self):
        """デフォルトは localhost"""
        
    def test_redis_port_default(self):
        """デフォルトは 6379"""
        
    def test_redis_password_optional(self):
        """パスワードは None がデフォルト"""
        
    def test_redis_database_default(self):
        """database デフォルトは 0"""

class TestRedisContainerConfig:
    """RedisContainerConfig のメソッドテスト"""
    
    def test_get_container_name_default(self):
        """デフォルト: repom_redis"""
        
    def test_get_container_name_custom(self):
        """カスタム値で上書き可能"""
        
    def test_get_volume_name_default(self):
        """デフォルト: repom_redis_data"""
        
    def test_get_volume_name_custom(self):
        """カスタム値で上書き可能"""
        
    def test_image_default(self):
        """デフォルト: redis:7-alpine"""
```

**テスト対象**:
- `config.redis.host`, `config.redis.port`, `config.redis.password`, `config.redis.database` のデフォルト値
- `config.redis.container.get_container_name()` の動作
- `config.redis.container.get_volume_name()` の動作

#### 2. `tests/unit_tests/test_repom_info_redis.py` （PostgreSQL パターンに倣う）

```python
class TestRedisConnectionTest:
    """test_redis_connection() 関数のテスト"""
    
    @patch('redis.Redis')
    def test_connection_success(self, mock_redis):
        """redis-py インストール済み + 接続成功"""
        # → "✓ Connected"
        
    def test_redis_py_not_installed(self):
        """redis-py 未インストール"""
        # ImportError → "⚠ redis-py not installed"
        
    @patch('redis.Redis')
    def test_connection_refused(self, mock_redis):
        """接続拒否時 (ConnectionError)"""
        # → "✗ Connection refused"
        
    @patch('redis.Redis')
    def test_other_error(self, mock_redis):
        """その他のエラー"""
        # → "✗ Error: {エラー名}"

class TestRepomInfoDisplay:
    """repom_info Redis 出力のテスト"""
    
    @patch('repom.scripts.repom_info.test_redis_connection')
    @patch('repom.scripts.repom_info.config')
    def test_redis_section_output(self, mock_config, mock_test):
        """Redis セクションが正しく出力されるか"""
```

**テスト対象**:
- `test_redis_connection()` の複数パターン（成功、未インストール、接続拒否、エラー）
- repom_info 出力フォーマット
- Redis 情報が正しく表示される

### 🟠 推奨テスト

#### 3. `tests/unit_tests/test_redis_manage.py` （redis/manage.py の config 統合）

```python
class TestRedisManagerConfig:
    """RedisManager が config から値を取得するか"""
    
    @patch('repom.redis.manage.config')
    def test_get_container_name_from_config(self, mock_config):
        """get_container_name() が config.redis.container.get_container_name() を呼び出す"""
        
    @patch('repom.redis.manage.config')
    def test_generate_docker_compose_uses_config(self, mock_config):
        """generate_docker_compose() が config 値を使用"""
        # image, container_name, ports, volumes をテスト
```

**テスト対象**:
- `RedisManager.get_container_name()` が config から取得
- `generate_docker_compose()` が config 値を反映
- `docker-compose.yml` 生成内容の検証

### 🟡 オプションテスト

#### 4. `tests/integration_tests/test_redis_docker.py` （実装後の検証）

```python
class TestRedisDockerIntegration:
    """実際の Redis コンテナでの統合テスト"""
    
    def test_redis_container_startup(self):
        """Redis コンテナが正常に起動するか"""
        
    def test_redis_connection_to_container(self):
        """redis-py で実コンテナに接続可能か"""
        
    def test_config_values_in_generated_compose(self):
        """docker-compose.yml に config 値が反映されているか"""
```

**テスト対象**:
- 実コンテナの起動・停止
- すべての config 値が反映されているか

### その他のテスト項目

#### CONFIG_HOOK テスト

```python
class TestRedisConfigHook:
    """CONFIG_HOOK による設定上書き"""
    
    @patch.dict(os.environ, {'CONFIG_HOOK': 'tests.fixtures.hook_custom_redis_config'})
    def test_custom_redis_config_applied(self):
        """カスタム config が apply されるか"""
```

### テスト実装の優先度順

| # | テストファイル | 優先度 | 実装タイミング |
|---|---|---|---|
| 1 | `test_config_redis.py` | 🔴必須 | Phase 1 完了後 |
| 2 | `test_repom_info_redis.py` | 🔴必須 | Phase 2 完了後 |
| 3 | `test_redis_manage.py` | 🟠推奨 | Phase 3 完了後 |
| 4 | `test_redis_docker.py` | 🟡オプション | 全 Phase 完了後 |
| 5 | CONFIG_HOOK テスト | 🟡オプション | 全 Phase 完了後 |

### テスト実行コマンド

```bash
# 必須テストのみ
poetry run pytest tests/unit_tests/test_config_redis.py tests/unit_tests/test_repom_info_redis.py

# 推奨テスト含む
poetry run pytest tests/unit_tests/test_config_redis.py tests/unit_tests/test_repom_info_redis.py tests/unit_tests/test_redis_manage.py

# 全テスト（統合テスト含む）
poetry run pytest tests/unit_tests/test_config_redis.py tests/unit_tests/test_repom_info_redis.py tests/unit_tests/test_redis_manage.py tests/integration_tests/test_redis_docker.py

# 全テスト実行（通常の pytest）
poetry run pytest
```

### Phase 0 関連（依存関係）

- `pyproject.toml` で `redis` をオプション依存として定義
- `poetry install -E redis` で redis オプションと共にインストール可能
- `redis` なしでも repom 基本機能は動作（repom_info は "⚠ redis-py not installed" と表示）

## 関連ドキュメント

- **guides/redis_manager_guide.md**: Redis 管理ガイド（Issue #041 で作成）
- **completed/041_redis_docker_integration.md**: Redis Docker 統合（前提 Issue）

---

## 実装上の注意点

### redis-py ライブラリ採用の理由

✅ **環境非依存**: 外部コマンド（redis-cli）に依存しない
✅ **OpenAI Codex 等で動作**: サンドボックス環境可対応
✅ **信頼性**: 実際のプロトコル通信で正確な接続確認
✅ **拡張性**: redis-py から他の Redis 操作も容易に追加可能
✅ **プロダクション対応**:実装用途でも使用されている成熟ライブラリ

### redis 依存関係をオプションにする理由

- repom は基本的には依存関係を最小化する
- Redis 機能（repom_info の Redis テスト、redis/manage.py）は必須ではない
- エンドユーザーは `poetry install -E redis` で明示的にオプト-イン
- 基本的な repom 機能は redis なしでも動作

### テスト設計

- redis-py が未インストール時は正常に "⚠ redis-py not installed" を返す（graceful）
- mock を使った unit test で redis-py がない状態をシミュレート可能
- integration test は実際の Redis コンテナで検証

## CONFIG_HOOK による環境別カスタマイズ

**参考**: `docs/guides/features/config_hook_guide.md`

PostgreSQL と同じパターンで、`.env` または `CONFIG_HOOK` 環境変数で config をカスタマイズ可能：

```bash
# .env ファイル
CONFIG_HOOK=myapp.config:hook_config
```

```python
# myapp/config.py - CONFIG_HOOK 関数の例
from repom.config import RepomConfig

def hook_config(config: RepomConfig) -> RepomConfig:
    """Redis を本番環境用に設定する例"""
    config.redis.host = 'redis.example.com'
    config.redis.port = 6380
    config.redis.password = 'production_secret'
    config.redis.container.host_port = 6380
    config.redis.container.container_name = 'myapp_redis'
    return config
```

---

## 備考

- **PostgreSQL パターンに統一**: `PostgresConfig` + `PostgresContainerConfig` と同じ構造を採用
- **CONFIG_HOOK に完全対応**: `config_hook_guide.md` の方法で環境別カスタマイズ可
- **互換性対応なし**: Redis 機能はまだ repom 利用パッケージで実装されていないため、後方互換性対応は必要ない
- **redis/manage.py の現状**:
  - ファイルパス: `repom/redis/manage.py` (242行)
  - ハードコード箇所: 41, 128-129, 142, 191-192行目で修正予定

