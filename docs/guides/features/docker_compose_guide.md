# Docker Compose 蝓ｺ逶､繧ｬ繧､繝・

縺薙・繧ｬ繧､繝峨〒縺ｯ縲〉epom 縺ｮ豎守畑 Docker Compose 蝓ｺ逶､繧剃ｽｿ縺｣縺ｦ縲√き繧ｹ繧ｿ繝縺ｪ Docker 迺ｰ蠅・ｒ讒狗ｯ峨☆繧区婿豕輔ｒ隱ｬ譏弱＠縺ｾ縺吶・

## 搭 逶ｮ谺｡

- [讎りｦ‐(#讎りｦ・
- [蝓ｺ譛ｬ逧・↑菴ｿ縺・婿](#蝓ｺ譛ｬ逧・↑菴ｿ縺・婿)
- [螳溯｣・ｾ・ Redis](#螳溯｣・ｾ・redis)
- [螳溯｣・ｾ・ MongoDB](#螳溯｣・ｾ・mongodb)
- [API 繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ](#api-繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ)

---

## 讎りｦ・

`basekit.docker_compose` is the shared Docker Compose generation utility now maintained in basekit.

### 荳ｻ縺ｪ讖溯・

- 笨・**蝙句ｮ牙・**: 繝・・繧ｿ繧ｯ繝ｩ繧ｹ縺ｧ險ｭ螳壹ｒ邂｡逅・
- 笨・**繝励Ο繧ｸ繧ｧ繧ｯ繝亥崋譛・*: CONFIG_HOOK 縺ｧ險ｭ螳壹ｒ繧ｫ繧ｹ繧ｿ繝槭う繧ｺ
- 笨・**蜍慕噪逕滓・**: 螳溯｡梧凾縺ｫ docker-compose.yml 繧堤函謌・
- 笨・**諡｡蠑ｵ蜿ｯ閭ｽ**: 莉ｻ諢上・ Docker 繧ｵ繝ｼ繝薙せ縺ｫ蟇ｾ蠢・

### 謠蝉ｾ帙け繝ｩ繧ｹ

```python
from basekit.docker_compose import (
    DockerComposeGenerator,  # docker-compose.yml 逕滓・蝎ｨ
    DockerService,            # 繧ｵ繝ｼ繝薙せ螳夂ｾｩ
    DockerVolume,             # Volume 螳夂ｾｩ
)
```

---

## 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿

### Step 1: 繧ｵ繝ｼ繝薙せ險ｭ螳壹ｒ螳夂ｾｩ

```python
from basekit.docker_compose import DockerService, DockerVolume

# 繧ｵ繝ｼ繝薙せ繧貞ｮ夂ｾｩ
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

# Volume 繧貞ｮ夂ｾｩ
data_volume = DockerVolume(name="postgres_data")
```

### Step 2: 逕滓・蝎ｨ縺ｧ docker-compose.yml 繧堤函謌・

```python
from basekit.docker_compose import DockerComposeGenerator
from pathlib import Path

# 逕滓・蝎ｨ繧剃ｽ懈・
generator = DockerComposeGenerator(version="3.8")
generator.add_service(postgres_service)
generator.add_volume(data_volume)

# 繝輔ぃ繧､繝ｫ縺ｫ譖ｸ縺崎ｾｼ縺ｿ
output_path = Path("data/my_project/docker-compose.generated.yml")
generator.write_to_file(output_path)
```

### Step 3: 譁・ｭ怜・縺ｨ縺励※蜿門ｾ暦ｼ医ユ繧ｹ繝育畑・・

```python
# YAML 繧呈枚蟄怜・縺ｨ縺励※蜿門ｾ・
yaml_content = generator.generate()
print(yaml_content)
```

蜃ｺ蜉帑ｾ具ｼ・
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

## 螳溯｣・ｾ・ Redis

### 1. Config 縺ｫ險ｭ螳壹ｒ霑ｽ蜉

```python
# repom/config.py
from dataclasses import dataclass, field

@dataclass
class RedisContainerConfig:
    """Redis Docker 繧ｳ繝ｳ繝・リ險ｭ螳・""
    container_name: Optional[str] = field(default=None)
    host_port: int = field(default=6379)
    image: str = field(default="redis:7-alpine")
    
    def get_container_name(self) -> str:
        return self.container_name or "repom_redis"
    
    def get_volume_name(self) -> str:
        return f"{self.get_container_name()}_data"

@dataclass
class RedisConfig:
    """Redis 險ｭ螳・""
    host: str = field(default='localhost')
    port: int = field(default=6379)
    container: RedisContainerConfig = field(default_factory=RedisContainerConfig)

class RepomConfig:
    def __init__(self):
        # ... 譌｢蟄倥・險ｭ螳・...
        self.redis = RedisConfig()
```

### 2. manage.py 繧剃ｽ懈・

```python
# repom/scripts/redis/manage.py
import subprocess
from pathlib import Path
from repom.config import config
from basekit.docker_compose import DockerComposeGenerator, DockerService, DockerVolume

def get_compose_dir() -> Path:
    """docker-compose.yml 縺ｮ菫晏ｭ伜・"""
    compose_dir = Path(config.data_path)
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir

def generate_docker_compose() -> DockerComposeGenerator:
    """config 縺九ｉ docker-compose.yml 逕滓・蝎ｨ繧剃ｽ懈・"""
    container = config.redis.container
    
    # Redis 繧ｵ繝ｼ繝薙せ繧貞ｮ夂ｾｩ
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
    
    # Docker Volume 繧貞ｮ夂ｾｩ
    data_volume = DockerVolume(name=container.get_volume_name())
    
    # 逕滓・蝎ｨ繧剃ｽ懈・
    generator = DockerComposeGenerator()
    generator.add_service(redis_service)
    generator.add_volume(data_volume)
    
    return generator

def generate():
    """docker-compose.yml 繧堤函謌・""
    generator = generate_docker_compose()
    compose_dir = get_compose_dir()
    output_path = compose_dir / "docker-compose.generated.yml"
    generator.write_to_file(output_path)
    
    print(f"笨・Generated: {output_path}")
    print(f"   Container: {config.redis.container.get_container_name()}")
    print(f"   Port: {config.redis.container.host_port}")

def start():
    """Redis 繧定ｵｷ蜍・""
    generate()
    
    print(f"正 Starting Redis container...")
    
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "up", "-d"],
        check=True,
        cwd=str(compose_dir)
    )

def stop():
    """Redis 繧貞●豁｢"""
    compose_dir = get_compose_dir()
    compose_file = compose_dir / "docker-compose.generated.yml"
    
    if not compose_file.exists():
        print("笞・・ docker-compose.generated.yml 縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ")
        return
    
    subprocess.run(
        ["docker-compose", "-f", str(compose_file), "down"],
        check=True,
        cwd=str(compose_dir)
    )
```

### 3. 繧ｳ繝槭Φ繝峨ｒ霑ｽ蜉

```toml
# pyproject.toml
[project.scripts]
redis_generate = "repom.scripts.redis.manage:generate"
redis_start = "repom.scripts.redis.manage:start"
redis_stop = "repom.scripts.redis.manage:stop"
```

### 4. CONFIG_HOOK 縺ｧ繧ｫ繧ｹ繧ｿ繝槭う繧ｺ

```python
# mine_py/config.py
def hook_config(config: RepomConfig) -> RepomConfig:
    # Redis 縺ｮ險ｭ螳壹ｂ繧ｫ繧ｹ繧ｿ繝槭う繧ｺ
    config.redis.container.container_name = "mine_py_redis"
    config.redis.container.host_port = 6380  # 繝昴・繝医ｒ縺壹ｉ縺・
    
    return config
```

---

## 螳溯｣・ｾ・ MongoDB

### DockerService 縺ｮ螳夂ｾｩ

```python
from basekit.docker_compose import DockerService, DockerVolume

# MongoDB 繧ｵ繝ｼ繝薙せ
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

# Volume 螳夂ｾｩ
data_volume = DockerVolume(name="mongodb_data")
config_volume = DockerVolume(name="mongodb_config")
```

---

## API 繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ

### DockerService

Docker 繧ｵ繝ｼ繝薙せ縺ｮ險ｭ螳壹ｒ陦ｨ縺吶ョ繝ｼ繧ｿ繧ｯ繝ｩ繧ｹ

**繝代Λ繝｡繝ｼ繧ｿ**:
- `name: str` - 繧ｵ繝ｼ繝薙せ蜷搾ｼ亥ｿ・茨ｼ・
- `image: str` - Docker 繧､繝｡繝ｼ繧ｸ・亥ｿ・茨ｼ・
- `container_name: str` - 繧ｳ繝ｳ繝・リ蜷搾ｼ亥ｿ・茨ｼ・
- `ports: List[str]` - 繝昴・繝医・繝・ヴ繝ｳ繧ｰ・井ｾ・ `["5432:5432"]`・・
- `environment: Dict[str, str]` - 迺ｰ蠅・､画焚
- `volumes: List[str]` - Volume 繝槭ャ繝斐Φ繧ｰ
- `healthcheck: Optional[Dict]` - 繝倥Ν繧ｹ繝√ぉ繝・け險ｭ螳・

**萓・*:
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

Docker Volume 縺ｮ險ｭ螳壹ｒ陦ｨ縺吶ョ繝ｼ繧ｿ繧ｯ繝ｩ繧ｹ

**繝代Λ繝｡繝ｼ繧ｿ**:
- `name: str` - Volume 蜷搾ｼ亥ｿ・茨ｼ・
- `driver: str` - 繝峨Λ繧､繝舌・・医ョ繝輔か繝ｫ繝・ `"local"`・・

**萓・*:
```python
volume = DockerVolume(name="my_data", driver="local")
```

### DockerComposeGenerator

docker-compose.yml 繧堤函謌舌☆繧九け繝ｩ繧ｹ

**繝｡繧ｽ繝・ラ**:
- `add_service(service: DockerService) -> self` - 繧ｵ繝ｼ繝薙せ繧定ｿｽ蜉
- `add_volume(volume: DockerVolume) -> self` - Volume 繧定ｿｽ蜉
- `generate() -> str` - YAML 譁・ｭ怜・繧堤函謌・
- `write_to_file(filepath: Path) -> None` - 繝輔ぃ繧､繝ｫ縺ｫ譖ｸ縺崎ｾｼ縺ｿ

**萓・*:
```python
generator = DockerComposeGenerator(version="3.8")
generator.add_service(my_service)
generator.add_volume(my_volume)

# 繝輔ぃ繧､繝ｫ縺ｫ譖ｸ縺崎ｾｼ縺ｿ
generator.write_to_file(Path("docker-compose.yml"))

# 縺ｾ縺溘・譁・ｭ怜・縺ｨ縺励※蜿門ｾ・
yaml_content = generator.generate()
```

---

## 繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ

### 1. CONFIG_HOOK 縺ｧ繝励Ο繧ｸ繧ｧ繧ｯ繝亥崋譛峨・險ｭ螳壹ｒ邂｡逅・

```python
# 笶・謔ｪ縺・ｾ・ 繝上・繝峨さ繝ｼ繝・
container_name = "postgres"

# 笨・濶ｯ縺・ｾ・ CONFIG_HOOK 縺ｧ蜍慕噪縺ｫ險ｭ螳・
def hook_config(config: RepomConfig) -> RepomConfig:
    config.postgres.container.container_name = "my_project_postgres"
    config.postgres.container.host_port = 5433
    return config
```

### 2. data/ 驟堺ｸ九↓菫晏ｭ・

```python
# 笨・謗ｨ螂ｨ: data/ 驟堺ｸ九↓菫晏ｭ・
compose_dir = Path(config.data_path)

# 笶・髱樊耳螂ｨ: scripts/ 縺ｫ菫晏ｭ假ｼ郁､・焚繝励Ο繧ｸ繧ｧ繧ｯ繝医〒陦晉ｪ・ｼ・
compose_dir = Path(__file__).parent
```

### 3. .generated 繧ｵ繝輔ぅ繝・け繧ｹ繧剃ｽｿ逕ｨ

```python
# 笨・謗ｨ螂ｨ: 蜍慕噪逕滓・繝輔ぃ繧､繝ｫ縺ｧ縺ゅｋ縺薙→繧呈・遉ｺ
output_path = compose_dir / "docker-compose.generated.yml"

# 笶・髱樊耳螂ｨ: 謇句虚邱ｨ髮・→蛹ｺ蛻･縺後▽縺九↑縺・
output_path = compose_dir / "docker-compose.yml"
```

### 4. .gitignore 縺ｫ霑ｽ蜉

```gitignore
# 蜍慕噪逕滓・繝輔ぃ繧､繝ｫ縺ｯ Git 邂｡逅・､・
data/*/docker-compose.generated.yml
data/*/postgresql_init/
data/*/redis_init/
```

---

## 繝医Λ繝悶Ν繧ｷ繝･繝ｼ繝・ぅ繝ｳ繧ｰ

### 逕滓・縺輔ｌ縺・YAML 縺御ｸ肴ｭ｣

```python
# 繝・ヰ繝・げ: 逕滓・蜀・ｮｹ繧堤｢ｺ隱・
generator = generate_docker_compose()
print(generator.generate())
```

### 繝代せ縺梧ｭ｣縺励￥縺ｪ縺・

```python
# 繝・ヰ繝・げ: 繝代せ繧堤｢ｺ隱・
compose_dir = get_compose_dir()
print(f"Compose dir: {compose_dir}")
print(f"Exists: {compose_dir.exists()}")
```

---

## 髢｢騾｣繝峨く繝･繝｡繝ｳ繝・

- **[PostgreSQL 繧ｻ繝・ヨ繧｢繝・・繧ｬ繧､繝云(../postgresql/postgresql_setup_guide.md)**: PostgreSQL 縺ｧ縺ｮ螳溯｣・ｾ・
- **[Issue #038](../../issue/active/038_postgresql_container_customization.md)**: 蝓ｺ逶､縺ｮ險ｭ險郁レ譎ｯ
- **[CONFIG_HOOK 繧ｬ繧､繝云(config_hook_guide.md)**: 險ｭ螳壹・繧ｫ繧ｹ繧ｿ繝槭う繧ｺ譁ｹ豕・

---

**菴懈・譌･**: 2026-02-22  
**蟇ｾ雎｡繝舌・繧ｸ繝ｧ繝ｳ**: repom v0.1.0+


