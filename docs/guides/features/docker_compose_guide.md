# Docker Compose 基盤ガイド

このガイドでは、repom の汎用 Docker Compose 基盤を使って、カスタムな Docker 環境を構築する方法を説明します。

## 📋 目次

- [概要](#概要)
- [基本的な使い方](#基本的な使い方)
- [実装例: Redis](#実装例-redis)
- [実装例: MongoDB](#実装例-mongodb)
- [API リファレンス](#api-リファレンス)

---

## 概要

`repom._/docker_compose.py` は、Docker Compose ファイルを動的に生成するための汎用基盤です。

### 主な機能

- ✅ **型安全**: データクラスで設定を管理
- ✅ **プロジェクト固有**: CONFIG_HOOK で設定をカスタマイズ
- ✅ **動的生成**: 実行時に docker-compose.yml を生成
- ✅ **拡張可能**: 任意の Docker サービスに対応

### 提供クラス

```python
from repom._.docker_compose import (
    DockerComposeGenerator,  # docker-compose.yml 生成器
    DockerService,            # サービス定義
    DockerVolume,             # Volume 定義
)
```

---

## 基本的な使い方

### Step 1: サービス設定を定義

```python
from repom._.docker_compose import DockerService, DockerVolume

# サービスを定義
postgres_service = DockerService(
    name="postgres",
    image="postgres:16-alpine",
    container_name="my_project_postgres",
    ports=["5432:5432"],
    environment={
        "POSTGRES_USER": "myuser",
        "POSTGRES_PASSWORD": "mypass",
        "POSTGRES_DB": "mydb",
    },
    volumes=[
        "postgres_data:/var/lib/postgresql/data",
    ],
    healthcheck={
        "test": '["CMD-SHELL", "pg_isready -U myuser"]',
        "interval": "5s",
        "timeout": "5s",
        "retries": 5,
    }
)

# Volume を定義
data_volume = DockerVolume(name="postgres_data")
```

### Step 2: 生成器で docker-compose.yml を生成

```python
from repom._.docker_compose import DockerComposeGenerator
from pathlib import Path

# 生成器を作成
generator = DockerComposeGenerator(version="3.8")
generator.add_service(postgres_service)
generator.add_volume(data_volume)

# ファイルに書き込み
output_path = Path("data/my_project/docker-compose.generated.yml")
generator.write_to_file(output_path)
```

### Step 3: 文字列として取得（テスト用）

```python
# YAML を文字列として取得
yaml_content = generator.generate()
print(yaml_content)
```

出力例：
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: my_project_postgres
    environment:
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypass
      POSTGRES_DB: mydb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myuser"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

---

## 実装例: Redis

### 1. Config に設定を追加

```python
# repom/config.py
from dataclasses import dataclass, field

@dataclass
class RedisContainerConfig:
    """Redis Docker コンテナ設定"""
    container_name: Optional[str] = field(default=None)
    host_port: int = field(default=6379)
    image: str = field(default="redis:7-alpine")
    
    def get_container_name(self) -> str:
        return self.container_name or "repom_redis"
    
    def get_volume_name(self) -> str:
        return f"{self.get_container_name()}_data"

@dataclass
class RedisConfig:
    """Redis 設定"""
    host: str = field(default='localhost')
    port: int = field(default=6379)
    container: RedisContainerConfig = field(default_factory=RedisContainerConfig)

class RepomConfig:
    def __init__(self):
        # ... 既存の設定 ...
        self.redis = RedisConfig()
```

### 2. manage.py を作成

```python
# repom/scripts/redis/manage.py
import subprocess
from pathlib import Path
from repom.config import config
from repom._.docker_compose import DockerComposeGenerator, DockerService, DockerVolume

def get_compose_dir() -> Path:
    """docker-compose.yml の保存先"""
    compose_dir = Path(config.data_path)
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir

def generate_docker_compose() -> DockerComposeGenerator:
    """config から docker-compose.yml 生成器を作成"""
    container = config.redis.container
    
    # Redis サービスを定義
    redis_service = DockerService(
        name="redis",
        image=container.image,
        container_name=container.get_container_name(),
        ports=[f"{container.host_port}:6379"],
        volumes=[
            f"{container.get_volume_name()}:/data",
        ],
        healthcheck={
            "test": '["CMD", "redis-cli", "ping"]',
            "interval": "5s",
            "timeout": "3s",
            "retries": 5,
        }
    )
    
    # Docker Volume を定義
    data_volume = DockerVolume(name=container.get_volume_name())
    
    # 生成器を作成
    generator = DockerComposeGenerator()
    generator.add_service(redis_service)
    generator.add_volume(data_volume)
    
    return generator

def generate():
    """docker-compose.yml を生成"""
    generator = generate_docker_compose()
    compose_dir = get_compose_dir()
    output_path = compose_dir / "docker-compose.generated.yml"
    generator.write_to_file(output_path)
    
    print(f"✅ Generated: {output_path}")
    print(f"   Container: {config.redis.container.get_container_name()}")
    print(f"   Port: {config.redis.container.host_port}")

def start():
    """Redis を起動"""
    generate()
    
    print(f"🐳 Starting Redis container...")
    
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "up", "-d"],
        check=True,
        cwd=str(compose_dir)
    )

def stop():
    """Redis を停止"""
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    
    if not compose_file.exists():
        print("⚠️  docker-compose.generated.yml が見つかりません")
        return
    
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "down"],
        check=True,
        cwd=str(compose_dir)
    )
```

### 3. コマンドを追加

```toml
# pyproject.toml
[project.scripts]
redis_generate = "repom.scripts.redis.manage:generate"
redis_start = "repom.scripts.redis.manage:start"
redis_stop = "repom.scripts.redis.manage:stop"
```

### 4. CONFIG_HOOK でカスタマイズ

```python
# mine_py/config.py
def hook_config(config: RepomConfig) -> RepomConfig:
    # Redis の設定もカスタマイズ
    config.redis.container.container_name = "mine_py_redis"
    config.redis.container.host_port = 6380  # ポートをずらす
    
    return config
```

---

## 実装例: MongoDB

### DockerService の定義

```python
from repom._.docker_compose import DockerService, DockerVolume

# MongoDB サービス
mongo_service = DockerService(
    name="mongodb",
    image="mongo:7",
    container_name="my_project_mongodb",
    ports=["27017:27017"],
    environment={
        "MONGO_INITDB_ROOT_USERNAME": "admin",
        "MONGO_INITDB_ROOT_PASSWORD": "password",
        "MONGO_INITDB_DATABASE": "mydb",
    },
    volumes=[
        "mongodb_data:/data/db",
        "mongodb_config:/data/configdb",
    ],
    healthcheck={
        "test": '["CMD", "mongosh", "--eval", "db.adminCommand(\'ping\')"]',
        "interval": "10s",
        "timeout": "5s",
        "retries": 5,
    }
)

# Volume 定義
data_volume = DockerVolume(name="mongodb_data")
config_volume = DockerVolume(name="mongodb_config")
```

---

## API リファレンス

### DockerService

Docker サービスの設定を表すデータクラス

**パラメータ**:
- `name: str` - サービス名（必須）
- `image: str` - Docker イメージ（必須）
- `container_name: str` - コンテナ名（必須）
- `ports: List[str]` - ポートマッピング（例: `["5432:5432"]`）
- `environment: Dict[str, str]` - 環境変数
- `volumes: List[str]` - Volume マッピング
- `healthcheck: Optional[Dict]` - ヘルスチェック設定

**例**:
```python
service = DockerService(
    name="myservice",
    image="myimage:latest",
    container_name="my_container",
    ports=["8080:80"],
    environment={"KEY": "value"},
    volumes=["data:/app/data"],
    healthcheck={"test": '["CMD", "curl", "-f", "http://localhost/health"]'}
)
```

### DockerVolume

Docker Volume の設定を表すデータクラス

**パラメータ**:
- `name: str` - Volume 名（必須）
- `driver: str` - ドライバー（デフォルト: `"local"`）

**例**:
```python
volume = DockerVolume(name="my_data", driver="local")
```

### DockerComposeGenerator

docker-compose.yml を生成するクラス

**メソッド**:
- `add_service(service: DockerService) -> self` - サービスを追加
- `add_volume(volume: DockerVolume) -> self` - Volume を追加
- `generate() -> str` - YAML 文字列を生成
- `write_to_file(filepath: Path) -> None` - ファイルに書き込み

**例**:
```python
generator = DockerComposeGenerator(version="3.8")
generator.add_service(my_service)
generator.add_volume(my_volume)

# ファイルに書き込み
generator.write_to_file(Path("docker-compose.yml"))

# または文字列として取得
yaml_content = generator.generate()
```

---

## ベストプラクティス

### 1. CONFIG_HOOK でプロジェクト固有の設定を管理

```python
# ❌ 悪い例: ハードコード
container_name = "postgres"

# ✅ 良い例: CONFIG_HOOK で動的に設定
def hook_config(config: RepomConfig) -> RepomConfig:
    config.postgres.container.container_name = "my_project_postgres"
    config.postgres.container.host_port = 5433
    return config
```

### 2. data/ 配下に保存

```python
# ✅ 推奨: data/ 配下に保存
compose_dir = Path(config.data_path)

# ❌ 非推奨: scripts/ に保存（複数プロジェクトで衝突）
compose_dir = Path(__file__).parent
```

### 3. .generated サフィックスを使用

```python
# ✅ 推奨: 動的生成ファイルであることを明示
output_path = compose_dir / "docker-compose.generated.yml"

# ❌ 非推奨: 手動編集と区別がつかない
output_path = compose_dir / "docker-compose.yml"
```

### 4. .gitignore に追加

```gitignore
# 動的生成ファイルは Git 管理外
data/*/docker-compose.generated.yml
data/*/postgresql_init/
data/*/redis_init/
```

---

## トラブルシューティング

### 生成された YAML が不正

```python
# デバッグ: 生成内容を確認
generator = generate_docker_compose()
print(generator.generate())
```

### パスが正しくない

```python
# デバッグ: パスを確認
compose_dir = get_compose_dir()
print(f"Compose dir: {compose_dir}")
print(f"Exists: {compose_dir.exists()}")
```

---

## 関連ドキュメント

- **[PostgreSQL セットアップガイド](../postgresql/postgresql_setup_guide.md)**: PostgreSQL での実装例
- **[Issue #038](../../issue/active/038_postgresql_container_customization.md)**: 基盤の設計背景
- **[CONFIG_HOOK ガイド](config_hook_guide.md)**: 設定のカスタマイズ方法

---

**作成日**: 2026-02-22  
**対象バージョン**: repom v0.1.0+
