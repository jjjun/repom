# Redis Manager 実装ガイド（fast-domain 向け）

**対象**: fast-domain プロジェクトで RedisManager を実装する開発者  
**前提**: repom の DockerManager 基盤を使用  

---

## 📋 実装チェックリスト

- [ ] RedisManager クラス作成
- [ ] docker-compose.yml 生成ロジック実装
- [ ] CLI 統合 (poetry run redis_start/stop/remove)
- [ ] テストケース追加
- [ ] ドキュメント作成

---

## 🏗️ RedisManager クラス実装テンプレート

### ファイル位置

```
fast-domain/src/fast_domain/docker/
├── __init__.py
├── redis_manager.py          ← 新規作成
└── docker-compose.template.yml
```

### 実装コード

```python
# fast-domain/src/fast_domain/docker/redis_manager.py

import subprocess
from pathlib import Path

from repom._ import docker_manager as dm


class RedisManager(dm.DockerManager):
    """Redis コンテナ管理（Docker Manager 基盤を使用）
    
    docker-compose による start/stop/remove は DockerManager から継承
    """
    
    def __init__(self, compose_dir: Path):
        """初期化
        
        Args:
            compose_dir: docker-compose.yml の配置ディレクトリ
        """
        self.compose_dir = compose_dir
        self.container_name = "fast_domain_redis"
    
    def get_container_name(self) -> str:
        """Redis コンテナ名を返す"""
        return self.container_name
    
    def get_compose_file_path(self) -> Path:
        """docker-compose.yml のパスを返す"""
        compose_file = self.compose_dir / "docker-compose.generated.yml"
        if not compose_file.exists():
            raise FileNotFoundError(
                f"Compose file not found: {compose_file}\n"
                f"Hint: Run the generate command first"
            )
        return compose_file
    
    def wait_for_service(self, max_retries: int = 30) -> None:
        """Redis の起動を待機（redis-cli ping による確認）
        
        Args:
            max_retries: 最大リトライ秒数（デフォルト: 30秒）
        
        Raises:
            TimeoutError: max_retries 秒以内に起動しなかった
        """
        container_name = self.get_container_name()
        
        def check_redis_ready():
            try:
                result = subprocess.run(
                    ["docker", "exec", container_name, "redis-cli", "ping"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False
                )
                # redis-cli ping は "PONG\n" を返す
                return result.returncode == 0 and "PONG" in result.stdout
            except Exception:
                return False
        
        dm.DockerCommandExecutor.wait_for_readiness(
            check_redis_ready,
            max_retries=max_retries,
            service_name="Redis"
        )
    
    def print_connection_info(self) -> None:
        """Redis 接続情報を表示"""
        print()
        print("📦 Redis Connection:")
        print(f"  Host: localhost")
        print(f"  Port: 6379")
        print(f"  Database: 0 (default)")
```

---

## 📝 使用例

### 1. 基本的な操作

```python
from pathlib import Path
from fast_domain.docker.redis_manager import RedisManager

# 初期化
compose_dir = Path.cwd() / "infrastructure"
manager = RedisManager(compose_dir)

# 起動
manager.start()
# 出力:
# 🐳 Starting fast_domain_redis container...
# ⏳ Waiting for service to be ready...
# ✅ Redis is ready

# 接続情報表示
manager.print_connection_info()

# ステータス確認
if manager.is_running():
    print("Redis is running")

# 停止
manager.stop()

# 削除
manager.remove()
```

### 2. CLI コマンド統合

```bash
poetry run redis_start
poetry run redis_stop
poetry run redis_remove
```

---

## 🔧 generate() 関数実装例

```python
# fast-domain/src/fast_domain/docker/redis_manager.py に追加

def generate_docker_compose() -> dict:
    """docker-compose.yml 生成"""
    return {
        "version": "3.8",
        "services": {
            "redis": {
                "image": "redis:7-alpine",
                "container_name": "fast_domain_redis",
                "ports": ["6379:6379"],
                "volumes": [
                    "fast_domain_redis_data:/data"
                ],
                "command": "redis-server --appendonly yes"
            }
        },
        "volumes": {
            "fast_domain_redis_data": {}
        }
    }


def generate(compose_dir: Path):
    """docker-compose.yml を生成"""
    import json
    
    generator_func = generate_docker_compose
    compose_config = generator_func()
    compose_file = compose_dir / "docker-compose.generated.yml"
    
    # YAML に変換して保存
    import yaml
    compose_file.write_text(
        yaml.dump(compose_config, default_flow_style=False),
        encoding="utf-8"
    )
    
    print(f"✅ Generated: {compose_file}")
    print()
    print("📦 Redis Service:")
    print(f"  Container: fast_domain_redis")
    print(f"  Port: 6379")
    print(f"  Volume: fast_domain_redis_data")
```

---

## ✅ テスト例

```python
# fast-domain/tests/test_redis_manager.py

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

import pytest

from fast_domain.docker.redis_manager import RedisManager


class TestRedisManagerInitialization:
    """Test RedisManager initialization"""
    
    def test_redis_manager_instantiation(self):
        """Test creating RedisManager instance"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            assert manager is not None
            assert manager.get_container_name() == "fast_domain_redis"


class TestRedisManagerWaitForService:
    """Test wait_for_service method"""
    
    def test_wait_for_service_immediate_success(self):
        """Test wait_for_service succeeds immediately"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            # Mock docker exec to always succeed with PONG
            with patch.object(subprocess, 'run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="PONG\n"
                )
                
                # Should not raise
                manager.wait_for_service(max_retries=2)
    
    
    def test_wait_for_service_timeout(self):
        """Test wait_for_service timeout"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            # Mock docker exec to always fail
            with patch.object(subprocess, 'run') as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="")
                
                with pytest.raises(TimeoutError):
                    manager.wait_for_service(max_retries=1)


class TestRedisManagerInheritance:
    """Test inheritance from DockerManager"""
    
    def test_has_docker_manager_methods(self):
        """Test RedisManager has inherited DockerManager methods"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            # Verify methods exist via inheritance
            assert hasattr(manager, 'start')
            assert hasattr(manager, 'stop')
            assert hasattr(manager, 'remove')
            assert hasattr(manager, 'status')
            assert hasattr(manager, 'is_running')
            assert callable(manager.start)
```

---

## 📦 依存関係

```toml
# pyproject.toml に追加
[dependencies]
repom = { path = "../repom" }  # 共通基盤
pyyaml = "^6.0"
```

---

## 🎯 実装ステップ

### Step 1: ファイル構造作成
```bash
mkdir -p src/fast_domain/docker
touch src/fast_domain/docker/__init__.py
touch src/fast_domain/docker/redis_manager.py
```

### Step 2: RedisManager 実装
- `get_container_name()` 実装
- `get_compose_file_path()` 実装
- `wait_for_service()` 実装（redis-cli ping）

### Step 3: CLI 統合
```python
# pyproject.toml
[tool.poetry.scripts]
redis_generate = "fast_domain.docker.redis_manager:generate"
redis_start = "fast_domain.docker.redis_manager:start"
redis_stop = "fast_domain.docker.redis_manager:stop"
redis_remove = "fast_domain.docker.redis_manager:remove"
```

### Step 4: テスト追加
- RedisManager の unit test
- docker-compose.yml の生成テスト

---

## 🚀 期待される削減効果

| メトリック | 削減前 | 削減後 | 削減率 |
|----------|--------|--------|---------|
| Redis 管理コード | ~150行 | ~60行 | **60% 削減** |
| テストコード | 独立型 | 共通基盤利用 | コード共有化 |

---

**実装予想時間**: 1-2時間  
**テスト数目安**: 8-12個  
**参考**: [PostgreSQL 統合例](../../features/docker_manager_guide.md)
