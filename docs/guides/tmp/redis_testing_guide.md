# Redis Manager テストガイド（fast-domain 向け）

**対象**: fast-domain で RedisManager のテストを実装する開発者  

---

## 📋 テストチェックリスト

- [ ] Unit テスト：RedisManager クラス
- [ ] Integration テスト：ライフサイクル
- [ ] CLI テスト：poetry run redis_* コマンド
- [ ] Docker テスト：実際のコンテナ操作（CI/CD）

---

## Unit テスト例

### 1. RedisManager 初期化テスト

```python
# tests/test_redis_manager.py

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

import pytest

from fast_domain.docker.redis_manager import RedisManager


class TestRedisManagerInitialization:
    """RedisManager の初期化テスト"""
    
    def test_redis_manager_instantiation(self):
        """インスタンス作成テスト"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            assert manager is not None
            assert manager.get_container_name() == "fast_domain_redis"
    
    
    def test_get_container_name(self):
        """コンテナ名取得テスト"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            assert manager.get_container_name() == "fast_domain_redis"
            assert isinstance(manager.get_container_name(), str)
```

### 2. Compose ファイルパステスト

```python
class TestRedisManagerComposePath:
    """docker-compose ファイルパス処理テスト"""
    
    def test_get_compose_file_path_not_found(self):
        """Compose ファイルが見つからない場合"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            # ファイルが存在しないので例外
            with pytest.raises(FileNotFoundError) as exc_info:
                manager.get_compose_file_path()
            
            assert "docker-compose.generated.yml" in str(exc_info.value)
    
    
    def test_get_compose_file_path_exists(self):
        """Compose ファイルが存在する場合"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.generated.yml"
            compose_file.write_text("version: '3.8'\n")
            
            manager = RedisManager(compose_dir)
            
            result = manager.get_compose_file_path()
            assert result == compose_file
            assert result.exists()
```

### 3. wait_for_service テスト

```python
class TestRedisManagerWaitForService:
    """Redis readiness check テスト"""
    
    def test_wait_for_service_immediate_success(self):
        """すぐに成功する場合"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            with patch.object(subprocess, 'run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="PONG\n"
                )
                
                # 例外が発生しないこと
                manager.wait_for_service(max_retries=2)
    
    
    def test_wait_for_service_success_after_retries(self):
        """リトライ後に成功する場合"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            with patch.object(subprocess, 'run') as mock_run:
                # 最初は失敗、2回目から成功
                mock_run.side_effect = [
                    MagicMock(returncode=1, stdout=""),  # 失敗
                    MagicMock(returncode=0, stdout="PONG\n"),  # 成功
                ]
                
                # 例外が発生しないこと
                manager.wait_for_service(max_retries=3)
    
    
    def test_wait_for_service_timeout(self):
        """タイムアウトする場合"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            with patch.object(subprocess, 'run') as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="")
                
                with pytest.raises(TimeoutError):
                    manager.wait_for_service(max_retries=1)
    
    
    def test_wait_for_service_pong_check(self):
        """PONG 応答の確認テスト"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            with patch.object(subprocess, 'run') as mock_run:
                # returncode は 0 だが PONG がない場合
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="ERROR\n"
                )
                
                # PONG がないのでタイムアウト
                with pytest.raises(TimeoutError):
                    manager.wait_for_service(max_retries=1)
```

### 4. 継承テスト

```python
class TestRedisManagerInheritance:
    """DockerManager からのメソッド継承テスト"""
    
    def test_has_docker_manager_methods(self):
        """継承メソッドの存在確認"""
        with TemporaryDirectory() as tmpdir:
            manager = RedisManager(Path(tmpdir))
            
            # メソッドが存在すること
            assert hasattr(manager, 'start')
            assert hasattr(manager, 'stop')
            assert hasattr(manager, 'remove')
            assert hasattr(manager, 'status')
            assert hasattr(manager, 'is_running')
            
            # すべて callable であること
            assert callable(manager.start)
            assert callable(manager.stop)
            assert callable(manager.remove)
            assert callable(manager.status)
            assert callable(manager.is_running)
```

---

## Integration テスト例

### Redis ライフサイクルテスト

```python
class TestRedisManagerLifecycle:
    """Redis の完全なライフサイクルテスト"""
    
    def test_redis_full_lifecycle_mocked(self):
        """完全なライフサイクル（モック使用）"""
        with TemporaryDirectory() as tmpdir:
            compose_dir = Path(tmpdir)
            compose_file = compose_dir / "docker-compose.generated.yml"
            compose_file.write_text("version: '3.8'\n")
            
            manager = RedisManager(compose_dir)
            
            # start のモック
            with patch.object(subprocess, 'run') as mock_run, \
                 patch.object(manager, 'wait_for_service'):
                mock_run.return_value = MagicMock(returncode=0)
                manager.start()
                
                # docker-compose up が呼ばれること
                assert mock_run.called
```

---

## CLI テスト例

### CLI コマンドテスト

```python
class TestRedisManagerCLI:
    """CLI コマンド統合テスト"""
    
    def test_cli_generate_command_exists(self):
        """generate コマンドが存在すること"""
        from fast_domain.docker.redis_manager import generate
        
        assert callable(generate)
    
    
    def test_cli_start_command_exists(self):
        """start コマンドが存在すること"""
        from fast_domain.docker.redis_manager import start
        
        assert callable(start)
    
    
    def test_cli_stop_command_exists(self):
        """stop コマンドが存在すること"""
        from fast_domain.docker.redis_manager import stop
        
        assert callable(stop)
    
    
    def test_cli_remove_command_exists(self):
        """remove コマンドが存在すること"""
        from fast_domain.docker.redis_manager import remove
        
        assert callable(remove)
```

---

## Docker Integration テスト（CI/CD 環境）

### 実際のコンテナテスト

```python
@pytest.mark.docker  # テストマーク付き
class TestRedisManagerDocker:
    """実際の Docker を使用したテスト"""
    
    @pytest.fixture
    def redis_manager(self, tmp_path):
        """RedisManager フィクスチャ"""
        # docker-compose.yml を生成
        compose_dir = tmp_path
        compose_file = compose_dir / "docker-compose.generated.yml"
        compose_file.write_text("""
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    container_name: test_redis
    ports:
      - "6379:6379"
""")
        return RedisManager(compose_dir)
    
    
    def test_redis_start_actual(self, redis_manager):
        """実際に Redis を起動テスト"""
        try:
            redis_manager.start()
            
            # Redis が実行中か確認
            assert redis_manager.is_running()
            
            # redis-cli で接続確認
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True
            )
            assert "PONG" in result.stdout
        finally:
            # クリーンアップ
            redis_manager.stop()
            redis_manager.remove()
    
    
    def test_redis_stop_actual(self, redis_manager):
        """実際に Redis を停止テスト"""
        redis_manager.start()
        redis_manager.stop()
        
        # 停止しているか確認
        assert not redis_manager.is_running()
```

---

## テスト実行コマンド

```bash
# Unit テストのみ実行
poetry run pytest tests/test_redis_manager.py -v

# Docker テストを含めて実行
poetry run pytest tests/test_redis_manager.py -v -m docker

# カバレッジ付きで実行
poetry run pytest tests/test_redis_manager.py --cov=fast_domain.docker

# 特定のテストクラスのみ実行
poetry run pytest tests/test_redis_manager.py::TestRedisManagerWaitForService -v
```

---

## テストケース一覧（推奨）

| # | テストケース | 優先度 | モック | 実Docker |
|----|------------|--------|--------|----------|
| 1 | インスタンス作成 | 🔴高 | ✅ | - |
| 2 | コンテナ名取得 | 🔴高 | ✅ | - |
| 3 | Compose ファイルチェック | 🔴高 | ✅ | - |
| 4 | redis-cli ping 確認 | 🔴高 | ✅ | - |
| 5 | タイムアウト処理 | 🟡中 | ✅ | - |
| 6 | メソッド継承確認 | 🟢低 | ✅ | - |
| 7 | 完全ライフサイクル | 🟡中 | ✅ | ✅ |
| 8 | 実際の Docker 起動 | 🔴高 | - | ✅ |

---

## pytest 設定例

```ini
# pytest.ini または pyproject.toml

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
addopts = "-v --tb=short"
markers = [
    "docker: tests that require Docker",
    "unit: unit tests (fast)",
]
```

---

## GitHub Actions 例

```yaml
name: Redis Manager Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      docker:
        image: docker:latest
        options: --privileged
    
    steps:
      - uses: actions/checkout@v3
      
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: poetry install
      
      - name: Run unit tests
        run: poetry run pytest tests/test_redis_manager.py -m "not docker"
      
      - name: Run Docker tests
        run: poetry run pytest tests/test_redis_manager.py -m docker
```

---

**参考**: [PostgreSQL テスト実装](../../repom/postgres/manage.py)
