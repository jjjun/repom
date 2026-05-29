# Docker 管理スクリプト統一化による削減効果分析

## 📊 現状の行数分析

### PostgreSQL（repom）

| セクション | 行数 | 説明 |
|-----------|------|------|
| **Imports** | 11 | standard libs + config |
| **get_compose_dir()** | 8 | - |
| **get_init_dir()** | 9 | PostgreSQL特有 |
| **generate_pgadmin_servers_json()** | 21 | PostgreSQL特有 |
| **generate_docker_compose()** | 56 | PostgreSQL特有（複数サービス） |
| **generate_init_sql()** | 15 | PostgreSQL特有 |
| **generate()** | 39 | 混合（特有 + 共通） |
| **start()** | 48 | **74%共通** |
| **stop()** | 24 | **100%共通** |
| **remove()** | 24 | **100%共通** |
| **wait_for_postgres()** | 25 | **サービス固有（pg_isready）** |
| **if __name__** | 18 | CLI インターフェース |
| **合計** | **355行** | - |

### Redis（fast-domain）

| セクション | 行数 | 説明 |
|-----------|------|------|
| **Imports** | 7 | standard libs |
| **start()** | 35 | **74%共通** |
| **stop()** | 19 | **100%共通** |
| **remove()** | 18 | **100%共通** |
| **status()** | 10 | **50%共通** |
| **wait_for_redis()** | 17 | **サービス固有（redis-cli ping）** |
| **_get_container_status()** | 16 | **100%共通** |
| **_ping_redis()** | 11 | **サービス固有（redis-cli）** |
| **if __name__** | 19 | CLI インターフェース |
| **合計** | **152行** | - |

---

## 🔍 関数単位の重複度分析

### 1. docker-compose コマンド実行（重複度: 100%）

```
=== PostgreSQL ===
start()
  - subprocess.run(["docker-compose", "-f", str(compose_file), "up", "-d"], ...)
  
stop()
  - subprocess.run(["docker-compose", "-f", str(compose_file), "stop"], ...)
  
remove()
  - subprocess.run(["docker-compose", "-f", str(compose_file), "down", "-v"], ...)

=== Redis ===
start()
  - subprocess.run(["docker-compose", "-f", str(compose_file), "up", "-d"], ...)
  
stop()
  - subprocess.run(["docker-compose", "-f", str(compose_file), "stop"], ...)
  
remove()
  - subprocess.run(["docker-compose", "-f", str(compose_file), "down"], ...)
```

**削減可能行数**: 約 20行（省略可能なエラーハンドリング含む）

---

### 2. Readiness Check パターン（重複度: 95%）

```
=== PostgreSQL ===
wait_for_postgres()
  - for i in range(max_retries):
  - subprocess.run(["docker", "exec", container_name, "pg_isready", "-U", user], ...)
  - if (i + 1) % 5 == 0: print(...)
  - time.sleep(1)
  - raise TimeoutError(...)

=== Redis ===
wait_for_redis()
  - for i in range(max_retries):
  - _ping_redis()  # docker exec redis-cli ping
  - if (i + 1) % 5 == 0: print(...)
  - time.sleep(1)
  - raise TimeoutError(...)
```

**削減可能行数**: 約 15行（ループ構造をテンプレ化）

---

### 3. エラーハンドリング（重複度: 100%）

```
共通パターン（全4箇所に存在）:

try:
    subprocess.run([...], check=True, cwd=str(compose_dir))
except subprocess.CalledProcessError as e:
    print(f"❌ Failed to ...: {e}")
    sys.exit(1)
except FileNotFoundError:
    print("❌ docker-compose command not found.")
    print("Please install Docker Desktop: ...")
    sys.exit(1)
```

**削減可能行数**: 約 18行（デコレータ or ユーティリティ化）

---

### 4. Compose ファイル存在チェック（重複度: 100%）

```
共通パターン（stop / remove で使用）:

if not compose_file.exists():
    print("⚠️  docker-compose.generated.yml が見つかりません")
    print(f"   Expected: {compose_file}")
    print()
    print("ヒント: 先に 'uv run postgres_generate' を実行してください")
    return
```

**削減可能行数**: 約 6行

---

### 5. コンテナステータス確認（重複度: 100%）

```
=== PostgreSQL ===
(wait_for_postgres 内に内装)

=== Redis ===
_get_container_status()
  - subprocess.run(["docker", "ps", "--filter", f"name={CONTAINER_NAME}", ...], ...)

status()
  - _get_container_status()
  - _ping_redis()
```

**削減可能行数**: 約 12行

---

### 6. ユーザーメッセージング／進捗表示（重複度: 90%）

```
共通パターン:

print("🐳 Starting PostgreSQL container...")
print("✅ PostgreSQL stopped")
print(f"⏳ Waiting for PostgreSQL to be ready...")
```

**削減可能行数**: 約 15行（メッセージ辞書化）

---

## 🎯 サービス固有実装（削減不可）

### PostgreSQL 特有

- `generate_docker_compose()` - 56行
- `generate_pgadmin_servers_json()` - 21行
- `generate_init_sql()` - 15行
- `wait_for_postgres()` - **5行**（pg_isready コマンドのみ）
- `get_init_dir()` - 9行

**小計**: 106行（削減不可）

### Redis 特有

- `_ping_redis()` - 11行（redis-cli ping）
- `wait_for_redis()` - **5行**（ループのみ）

**小計**: 16行（削減不可）

---

## 📈 削減効果の計算

### 共通化前の総行数

- PostgreSQL: 355行
- Redis: 152行
- **合計**: 507行

### 共通化後の推定行数

#### 共通基盤（現行: `basekit.docker_manager`）

この分析は当初 repom 内の共通化を前提に作成されたものですが、現在の汎用 Docker 管理基盤は `basekit.docker_manager` に移管済みです。repom 側の `PostgresManager` / `RedisManager` は public API を維持し、内部で basekit の基盤を利用します。

| コンポーネント | 行数 | 説明 |
|---------------|------|------|
| **DockerManager ABC** | 30 | 抽象基盤クラス |
| **DockerCommandExecutor** | 60 | docker-compose / docker コマンド実行ユーティリティ |
| **ReadinessChecker** | 30 | 汎用 readiness check |
| **エラーハンドリングデコレータ** | 25 | @handle_docker_errors など |
| **ユーティリティ関数** | 20 | print_xxx, wait_xxx などヘルパー |
| **実装例（PostgresManager）** | 40 | 参考実装 |
| **実装例（RedisManager）** | 30 | 参考実装 |
| **テスト** | 50 | 共通基盤のテスト |
| **合計** | **285行** | - |

#### PostgreSQL 簡潔版（`repom/postgres/manage.py`）

```python
from basekit.docker_manager import DockerManager, DockerCommandExecutor

class PostgresManager(DockerManager):
    def __init__(self, config: RepomConfig):
        self.config = config
    
    # 実装
```

| セクション | 行数 | 削減量 |
|-----------|------|--------|
| Imports | 6 | -5 |
| get_compose_dir() | 8 | 0 |
| get_init_dir() | 9 | 0 |
| generate_*（3関数） | 92 | 0 |
| PostgresManager クラス | 80 | -200 |
| start() | 15 | -33 |
| stop() | 8 | -16 |
| remove() | 8 | -16 |
| wait_for_service() | 10 | -15 |
| CLI | 12 | -6 |
| **合計** | **248行** | **-107** |

**削減率**: 30% (107 / 355)

#### Redis 簡潔版（fast-domain）

```python
from basekit.docker_manager import DockerManager

class RedisManager(DockerManager):
    def __init__(self, compose_dir: Path):
        self.compose_dir = compose_dir
    # 実装
```

| セクション | 行数 | 削減量 |
|-----------|------|--------|
| Imports | 4 | -3 |
| start() | 12 | -23 |
| stop() | 8 | -11 |
| remove() | 8 | -10 |
| status() | 5 | -5 |
| wait_for_service() | 8 | -9 |
| _ping_service() | 5 | -6 |
| CLI | 12 | -7 |
| **合計** | **62行** | **-90** |

**削減率**: 59% (90 / 152)

### 全体削減効果

| 項目 | 削減前 | 削減後 | 削減量 | 削減率 |
|------|--------|--------|--------|--------|
| PostgreSQL | 355行 | 248行 | **-107行** | **30%** |
| Redis | 152行 | 62行 | **-90行** | **59%** |
| 共通基盤 | 0行 | 285行 | - | - |
| **合計** | 507行 | 595行 | -2行 | -0.4% |

**注**: 共通基盤は再利用可能なインフラストラクチャなので、3番目のサービス（MongoDB など）を追加する際に効果が出ます。

### 3番目のサービス追加時の削減効果

```
MongoDB Manager: 約50-70行
  → 総行数: 595 + 50 = 645行（予測）
  vs 独立実装: 595 + 150 = 745行
  
削減効果: 100行（15%効率化）
```

---

## 🧪 推奨テストケース（20+個）

### 1. 共通基盤テスト（8個）

```python
# tests/unit_tests/docker_manager/test_docker_command_executor.py

def test_run_docker_compose_success():
    """docker-compose コマンド成功時"""

def test_run_docker_compose_not_found():
    """docker-compose コマンド不在（FileNotFoundError）"""

def test_run_docker_compose_failure():
    """docker-compose コマンド失敗（CalledProcessError）"""

def test_get_container_status_running():
    """コンテナ実行中のステータス取得"""

def test_get_container_status_stopped():
    """コンテナ停止時のステータス取得"""

def test_get_container_status_not_found():
    """コンテナが見つからない場合"""

def test_wait_for_readiness_success():
    """Readiness check 成功（即座）"""

def test_wait_for_readiness_timeout():
    """Readiness check タイムアウト"""
```

### 2. PostgreSQL専用テスト（5個）

```python
# tests/unit_tests/docker_manager/test_postgres_manager.py

def test_postgres_manager_start():
    """PostgreSQL 起動フロー（generate → start）"""

def test_postgres_manager_stop():
    """PostgreSQL 停止"""

def test_postgres_manager_remove():
    """PostgreSQL 削除（ボリューム含む）"""

def test_wait_for_postgres_success():
    """pg_isready 待機（成功）"""

def test_wait_for_postgres_failure():
    """pg_isready 待機（失敗）"""
```

### 3. Redis 専用テスト（5個）

```python
# tests/unit_tests/docker_manager/test_redis_manager.py

def test_redis_manager_start():
    """Redis 起動"""

def test_redis_manager_stop():
    """Redis 停止"""

def test_redis_manager_remove():
    """Redis 削除"""

def test_wait_for_redis_success():
    """redis-cli ping 待機（成功）"""

def test_wait_for_redis_failure():
    """redis-cli ping 待機（失敗）"""
```

### 4. 統合テスト（5個）

```python
# tests/integration_tests/test_docker_manager_integration.py

def test_postgres_full_lifecycle():
    """PostgreSQL: generate → start → stop → remove"""

def test_redis_full_lifecycle():
    """Redis: start → stop → remove（generate なし）"""

def test_concurrent_services():
    """複数サービスの並行操作（PostgreSQL + Redis）"""

def test_compose_file_not_found_handling():
    """compose ファイル不在時の処理"""

def test_error_recovery():
    """エラー発生後のリカバリ"""
```

### 5. エッジケーステスト（3個）

```python
def test_partial_compose_file_corruption():
    """compose.yml が壊れている場合"""

def test_container_name_special_chars():
    """コンテナ名に特殊文字がある場合"""

def test_very_slow_startup(slow_machine):
    """遅いマシンでの起動（max_retries > 60s）"""
```

### 6. 入力値検証テスト（3個）

```python
def test_invalid_compose_file_path():
    """無効なパスを指定"""

def test_invalid_container_name():
    """無効なコンテナ名"""

def test_negative_max_retries():
    """負の max_retries 値"""
```

---

## 💡 テストの追加価値

### 各テストの重要性

| テスト | 優先度 | 目的 | 既存カバー状況 |
|--------|--------|------|---------------|
| docker-compose 実行 | 🔴高 | コマンド実行の基本 | ❌ なし |
| FileNotFoundError | 🔴高 | Docker 未インストール対応 | ❌ なし |
| Readiness チェック | 🔴高 | 起動待機精度 | ⚠️ 手動テストのみ |
| タイムアウト処理 | 🟡中 | 起動失敗時の挙動 | ❌ なし |
| エラーメッセージ | 🟡中 | ユーザーガイダンス | ❌ なし |
| 並行操作 | 🟢低 | スケーラビリティ | ❌ なし |

---

## 📋 受け入れ基準の改善提案

現在の受け入れ基準（分析ドキュメント作成時）：

```markdown
1. 既存機能がすべて動作
2. コード行数削減（repom: 150行以上、fast-domain: 200行以上）
3. 新規テスト: 20+個追加
4. ドキュメント整備完了
```

**実装時の受け入れ基準（確定版）**:

```markdown
1. ✅ 既存機能がすべて動作（互換性テスト 100% パス）
   - repom/postgres/manage.py の全機能稼働
   - uv run postgres_* コマンド全て動作
   
2. ✅ コード行数削減
   - repom/postgres/manage.py: 355行 → 248行（-107, 30%）
   - 共通基盤: basekit.docker_manager （約300-400行）
   
3. ✅ 実 Docker テスト成功
   - 共通基盤テスト: 8個（docker-compose, readiness, status）
   - PostgreSQL テスト: 7個（start/stop/remove, generate, pg_isready）
   - 統合テスト: 5個（フルライフサイクル、エラーハンドリング）
   - **合計**: 20+個テスト（全て実 Docker で検証）
   
4. ✅ ドキュメント整備完了
   - `docs/guides/features/docker_manager_guide.md` - 使用ガイド
   - `docs/technical/docker_manager_phase1_implementation_guide.md` - 設計ドキュメント
   - コード内 docstring（充実）
```

---

## 🚀 今後の拡張可能性

### MongoDB への応用

```python
class MongoManager(DockerManager):
    def __init__(self, host_port: int = 27017):
        self.host_port = host_port
    
    def wait_for_service(self) -> None:
        """mongo ping による待機"""
        # 約 15行で実装可能
```

**導入コスト**: 約 60行（generate 含む）

### マルチコンテナシナリオ

```python
# docker-compose に複数サービスを含む場合
class DockerServiceGroup:
    def __init__(self):
        self.services = []
    
    def add_service(self, manager: DockerManager):
        self.services.append(manager)
    
    def start_all(self):
        # 一度に start、個別に wait_for_service
```

**拡張コスト**: 約 50行

---

**分析完了日**: 2026-02-23  
**対象バージョン**: repom v0.1.0 / fast-domain 最新
