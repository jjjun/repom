# Docker Manager 繧ｬ繧､繝・

**蟇ｾ雎｡**: 繝ｪ繝昴ず繝医Μ縺ｮ繧ｷ繧ｹ繝・Β繧堤炊隗｣縺励∝ｮｹ蝎ｨ邂｡逅・ｒ螳溯｣・☆繧矩幕逋ｺ閠・
**菴懈・譌･**: 2026-02-23

> **Note**: Docker 管理の汎用基盤は `basekit.docker_manager` に移管済みです。repom は `repom.postgres.manage` / `repom.redis.manage` の public API を維持しつつ、内部で basekit の基盤を利用します。新しく汎用 Manager を定義する場合は `basekit.docker_manager` を直接 import してください。

---

## 答 逶ｮ谺｡

1. [讎りｦ‐(#讎りｦ・
2. [蝓ｺ譛ｬ逧・↑菴ｿ縺・婿](#蝓ｺ譛ｬ逧・↑菴ｿ縺・婿)
3. [API 繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ](#api繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ)
4. [繧ｵ繝ｼ繝薙せ蝗ｺ譛峨・螳溯｣・(#繧ｵ繝ｼ繝薙せ蝗ｺ譛峨・螳溯｣・
5. [繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ](#繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ)
6. [螳溯｣・ｾ犠(#螳溯｣・ｾ・

---

## 讎りｦ・

Docker Manager 縺ｯ **隍・焚縺ｮ繧ｳ繝ｳ繝・リ繧ｵ繝ｼ繝薙せ繧堤ｵｱ荳逧・↓邂｡逅・☆繧句渕逶､** 繧呈署萓帙＠縺ｾ縺吶・

### 迚ｹ蠕ｴ

- 笨・**蜈ｱ騾壼渕逶､**: PostgreSQL縲ヽedis縲｀ongoDB 縺ｪ縺ｩ隍・焚繧ｵ繝ｼ繝薙せ縺ｫ蟇ｾ蠢・
- 笨・**繝・Φ繝励Ξ繝ｼ繝医Γ繧ｽ繝・ラ繝代ち繝ｼ繝ｳ**: 蜈ｱ騾壼・逅・+ 繧ｵ繝ｼ繝薙せ迚ｹ譛牙・逅・・蛻・屬
- 笨・**繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ**: Docker 荳榊惠縲√ヵ繧｡繧､繝ｫ隕九▽縺九ｉ縺壹√ち繧､繝繧｢繧ｦ繝医↑縺ｩ
- 笨・**蝣・欧縺ｪ蠕・ｩ溘Ο繧ｸ繝・け**: Readiness check 縺ｫ繧医ｋ遒ｺ螳溘↑襍ｷ蜍慕｢ｺ隱・

### 繧｢繝ｼ繧ｭ繝・け繝√Ε

```
DockerManager (ABC)
笏懌楳笏 start()          竊・繝・Φ繝励Ξ繝ｼ繝医Γ繧ｽ繝・ラ・亥・騾夲ｼ・
笏懌楳笏 stop()           竊・繝・Φ繝励Ξ繝ｼ繝医Γ繧ｽ繝・ラ・亥・騾夲ｼ・
笏懌楳笏 remove()         竊・繝・Φ繝励Ξ繝ｼ繝医Γ繧ｽ繝・ラ・亥・騾夲ｼ・
笏懌楳笏 status()         竊・蜈ｱ騾壼ｮ溯｣・ｼ医せ繝・・繧ｿ繧ｹ遒ｺ隱搾ｼ・
笏懌楳笏 is_running()     竊・蜈ｱ騾壼ｮ溯｣・ｼ・tatus() 縺ｮ alias・・
笏・
笏懌楳笏 [謚ｽ雎｡繝｡繧ｽ繝・ラ]
笏懌楳笏 get_container_name()              竊・繧ｵ繝悶け繝ｩ繧ｹ縺悟ｮ溯｣・
笏懌楳笏 get_compose_file_path()           竊・繧ｵ繝悶け繝ｩ繧ｹ縺悟ｮ溯｣・
笏披楳笏 wait_for_service()                竊・繧ｵ繝悶け繝ｩ繧ｹ縺悟ｮ溯｣・ｼ医し繝ｼ繝薙せ蝗ｺ譛会ｼ・
```

---

## 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿

### 1. 迢ｬ閾ｪ縺ｮ Manager 繧ｯ繝ｩ繧ｹ繧貞ｮ夂ｾｩ

```python
from pathlib import Path
from basekit import docker_manager as dm


class MyServiceManager(dm.DockerManager):
    """My service 縺ｮ繧ｳ繝ｳ繝・リ邂｡逅・""

    SERVICE_NAME = "my_service"
    INIT_SUBDIR = "my_service_init"
    GENERATE_COMMAND = "my_service_generate"

    def __init__(self, data_path: Path):
        super().__init__(data_path=data_path)
    
    def get_container_name(self) -> str:
        """繧ｳ繝ｳ繝・リ蜷阪ｒ霑斐☆"""
        return "my_service"
    
    def get_compose_file_path(self) -> Path:
        """docker-compose.yml 縺ｮ繝代せ繧定ｿ斐☆"""
        compose_file = self.get_compose_dir() / "docker-compose.yml"
        if not compose_file.exists():
            raise FileNotFoundError(f"Compose file not found: {compose_file}")
        return compose_file
    
    def wait_for_service(self, max_retries: int = 30) -> None:
        """繧ｵ繝ｼ繝薙せ縺ｮ襍ｷ蜍輔ｒ蠕・ｩ滂ｼ医し繝ｼ繝薙せ蝗ｺ譛峨・蛛･蜈ｨ諤ｧ遒ｺ隱搾ｼ・""
        def check_service_ready():
            try:
                # 萓・ my_service 縺ｮ API 縺ｫ繧｢繧ｯ繧ｻ繧ｹ
                result = subprocess.run(
                    ["curl", "-f", "http://localhost:8000/health"],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
                return result.returncode == 0
            except Exception:
                return False
        
        dm.DockerCommandExecutor.wait_for_readiness(
            check_service_ready,
            max_retries=max_retries,
            service_name="My Service"
        )
```

### 2. 繧ｳ繝ｳ繝・リ繧呈桃菴・

```python
from pathlib import Path
from my_app.services import MyServiceManager

# 蛻晄悄蛹・
data_path = Path.cwd() / "data"
manager = MyServiceManager(data_path)

# 襍ｷ蜍・
manager.start()
# 蜃ｺ蜉・
# 正 Starting my_service container...
# 竢ｳ Waiting for service to be ready...
# 笨・My Service is ready

# 迥ｶ諷狗｢ｺ隱・
if manager.is_running():
    print("Running")
else:
    print("Stopped")

# 蛛懈ｭ｢
manager.stop()
# 蜃ｺ蜉・
# 尅 Stopping my_service container...
# 笨・my_service stopped

# 蜑企勁・医・繝ｪ繝･繝ｼ繝繧ょ性繧・・
manager.remove()
# 蜃ｺ蜉・
# ｧｹ Removing my_service container and volumes...
# 笨・my_service removed
```

---

## API 繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ

### DockerManager

#### `start()` 竊・None

繧ｳ繝ｳ繝・リ繧定ｵｷ蜍輔＠縺ｾ縺吶・

**蜃ｦ逅・ヵ繝ｭ繝ｼ**:
1. compose 繝輔ぃ繧､繝ｫ縺ｮ蟄伜惠遒ｺ隱・
2. `docker-compose up -d` 繧貞ｮ溯｡・
3. `wait_for_service()` 縺ｧ襍ｷ蜍募ｾ・ｩ・
4. 繝ｦ繝ｼ繧ｶ繝ｼ繝｡繝・そ繝ｼ繧ｸ陦ｨ遉ｺ

**萓句､・*:
- `FileNotFoundError`: compose 繝輔ぃ繧､繝ｫ縺瑚ｦ九▽縺九ｉ縺ｪ縺・
- `subprocess.CalledProcessError`: docker-compose 螟ｱ謨・
- `TimeoutError`: 繧ｵ繝ｼ繝薙せ縺瑚ｵｷ蜍輔＠縺ｪ縺・ｼ・ax_retries 遘剃ｻ･荳雁ｾ・ｩ滂ｼ・

---

#### `stop()` 竊・None

繧ｳ繝ｳ繝・リ繧貞●豁｢縺励∪縺呻ｼ亥炎髯､縺励↑縺・ｼ峨・

**蜃ｦ逅・*:
1. compose 繝輔ぃ繧､繝ｫ縺ｮ蟄伜惠遒ｺ隱・
2. `docker-compose stop` 繧貞ｮ溯｡・
3. 繝ｦ繝ｼ繧ｶ繝ｼ繝｡繝・そ繝ｼ繧ｸ陦ｨ遉ｺ

**萓句､・*:
- `FileNotFoundError`: compose 繝輔ぃ繧､繝ｫ縺瑚ｦ九▽縺九ｉ縺ｪ縺・
- `subprocess.CalledProcessError`: docker-compose 螟ｱ謨・

---

#### `remove()` 竊・None

繧ｳ繝ｳ繝・リ縺ｨ繝懊Μ繝･繝ｼ繝繧貞炎髯､縺励∪縺吶・

**蜃ｦ逅・*:
1. compose 繝輔ぃ繧､繝ｫ縺ｮ蟄伜惠遒ｺ隱・
2. `docker-compose down -v` 繧貞ｮ溯｡・
3. 繝ｦ繝ｼ繧ｶ繝ｼ繝｡繝・そ繝ｼ繧ｸ陦ｨ遉ｺ

**萓句､・*:
- `FileNotFoundError`: compose 繝輔ぃ繧､繝ｫ縺瑚ｦ九▽縺九ｉ縺ｪ縺・
- `subprocess.CalledProcessError`: docker-compose 螟ｱ謨・

---

#### `status()` 竊・bool

繧ｳ繝ｳ繝・リ縺悟ｮ溯｡御ｸｭ縺九ｒ遒ｺ隱阪＠縺ｾ縺吶・

**霑斐ｊ蛟､**:
- `True`: 螳溯｡御ｸｭ
- `False`: 蛛懈ｭ｢荳ｭ

**螳溯｣・*:
```python
status = manager.status()
print("Running" if status else "Stopped")
```

---

#### `is_running()` 竊・bool

`status()` 縺ｮ alias 縺ｧ縺呻ｼ亥酔縺俶ｩ溯・・峨・

```python
# status() 縺ｨ is_running() 縺ｯ蜷後§
assert manager.status() == manager.is_running()
```

---

### DockerManager (謚ｽ雎｡繝｡繧ｽ繝・ラ)

繧ｵ繝悶け繝ｩ繧ｹ縺ｯ莉･荳九ｒ螳溯｣・☆繧句ｿ・ｦ√′縺ゅｊ縺ｾ縺吶・

#### `get_container_name()` 竊・str

**螳溯｣・ｾ・*:
```python
def get_container_name(self) -> str:
    return "my_service"
```

---

#### `get_compose_file_path()` 竊・Path

**螳溯｣・ｾ・*:
```python
def get_compose_file_path(self) -> Path:
    compose_file = self.get_compose_dir() / "docker-compose.yml"
    if not compose_file.exists():
        raise FileNotFoundError(f"Compose file not found: {compose_file}")
    return compose_file
```

---

#### `wait_for_service(max_retries: int = 30)` 竊・None

**螳溯｣・ｾ・* (PostgreSQL 縺ｮ蝣ｴ蜷・:
```python
def wait_for_service(self, max_retries: int = 30) -> None:
    def check_postgres_ready():
        try:
            result = subprocess.run(
                ["docker", "exec", self.get_container_name(), 
                 "pg_isready", "-U", "postgres"],
                capture_output=True,
                timeout=2,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    dm.DockerCommandExecutor.wait_for_readiness(
        check_postgres_ready,
        max_retries=max_retries,
        service_name="PostgreSQL"
    )
```

---

### DockerCommandExecutor

繧ｯ繝ｩ繧ｹ繝｡繧ｽ繝・ラ縺ｮ縺ｿ・医せ繝・・繝医Ξ繧ｹ・峨・

#### `run_docker_compose(command, compose_file, cwd=None, capture_output=False)` 竊・str | None

docker-compose 繧ｳ繝槭Φ繝峨ｒ螳溯｡後＠縺ｾ縺吶・

**繝代Λ繝｡繝ｼ繧ｿ**:
- `command`: 螳溯｡後さ繝槭Φ繝会ｼ井ｾ・ `"up -d"`縲～"stop"`・・
- `compose_file`: docker-compose.yml 縺ｮ繝代せ
- `cwd`: 菴懈･ｭ繝・ぅ繝ｬ繧ｯ繝医Μ・医ョ繝輔か繝ｫ繝・ compose_file 縺ｮ隕ｪ・・
- `capture_output`: True 縺ｪ繧・stdout 繧定ｿ斐☆

**霑斐ｊ蛟､**:
- `capture_output=True`: stdout 譁・ｭ怜・
- `capture_output=False`: None

**萓句､・*:
- `subprocess.CalledProcessError`: 繧ｳ繝槭Φ繝牙､ｱ謨・
- `FileNotFoundError`: docker-compose 繧ｳ繝槭Φ繝我ｸ榊惠

---

#### `get_container_status(container_name)` 竊・str

繧ｳ繝ｳ繝・リ縺ｮ迥ｶ諷九ｒ蜿門ｾ励＠縺ｾ縺吶・

**霑斐ｊ蛟､**:
- `"Up X minutes"` 縺ｪ縺ｩ: 螳溯｡御ｸｭ
- `"Exited"` 縺ｪ縺ｩ: 蛛懈ｭ｢荳ｭ
- `""` (遨ｺ譁・ｭ怜・): 隕九▽縺九ｉ縺ｪ縺・

---

#### `wait_for_readiness(check_func, max_retries=30, interval_sec=1, service_name="Service")`

豎守畑縺ｮ readiness check 繝ｫ繝ｼ繝励〒縺吶・

**繝代Λ繝｡繝ｼ繧ｿ**:
- `check_func`: 蛛･蜈ｨ諤ｧ遒ｺ隱埼未謨ｰ・・rue = 襍ｷ蜍募ｮ御ｺ・ｼ・
- `max_retries`: 譛螟ｧ繝ｪ繝医Λ繧､遘呈焚
- `interval_sec`: 繝ｪ繝医Λ繧､髢馴囈・育ｧ抵ｼ・
- `service_name`: 繧ｵ繝ｼ繝薙せ蜷搾ｼ医Γ繝・そ繝ｼ繧ｸ陦ｨ遉ｺ逕ｨ・・

**萓句､・*:
- `TimeoutError`: max_retries 遘剃ｻ･蜀・↓襍ｷ蜍輔＠縺ｪ縺九▲縺・

---

## 繧ｵ繝ｼ繝薙せ蝗ｺ譛峨・螳溯｣・

### PostgreSQL 縺ｮ萓・

[repom/postgres/manage.py](../../../repom/postgres/manage.py) 縺ｮ `PostgresManager` 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

```python
from basekit import docker_manager as dm

class PostgresManager(dm.DockerManager):
    SERVICE_NAME = "postgres"
    INIT_SUBDIR = "postgresql_init"
    GENERATE_COMMAND = "postgres_generate"

    def __init__(self, config: RepomConfig):
        super().__init__(data_path=config.data_path)
        self.config = config
    
    def get_container_name(self) -> str:
        return f"repom_{self.config.postgres.container_name}"
    
    # ... (逵∫払)
```

**險ｭ螳壹・蜿門ｾ怜・**: `repom.config.RepomConfig`

### Redis 縺ｮ萓具ｼ・ast-domain・・

螟夜Κ繝励Ο繧ｸ繧ｧ繧ｯ繝茨ｼ・ast-domain・峨〒 `RedisManager` 繧貞ｮ夂ｾｩ縺励∪縺吶・

```python
# fast-domain/src/fast_domain/docker/redis_manager.py
from basekit import docker_manager as dm

class RedisManager(dm.DockerManager):
    SERVICE_NAME = "redis"
    INIT_SUBDIR = "redis_init"
    GENERATE_COMMAND = "redis_generate"

    def __init__(self, data_path: Path):
        super().__init__(data_path=data_path)
    
    def get_container_name(self) -> str:
        return "fast_domain_redis"
    
    # ... (逵∫払)
```

---

## 繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ

### 1. Docker 譛ｪ繧､繝ｳ繧ｹ繝医・繝ｫ

**繧ｨ繝ｩ繝ｼ**: `FileNotFoundError: docker-compose command not found`

**蟇ｾ蠢・*:
```python
try:
    manager.start()
except FileNotFoundError:
    print("笶・Docker Desktop 縺後う繝ｳ繧ｹ繝医・繝ｫ縺輔ｌ縺ｦ縺・∪縺帙ｓ")
    print("   https://www.docker.com/products/docker-desktop/")
    sys.exit(1)
```

### 2. Compose 繝輔ぃ繧､繝ｫ 繧定ｦ九▽縺九ｉ縺ｪ縺・

**繧ｨ繝ｩ繝ｼ**: `FileNotFoundError: Compose file not found: .../docker-compose.yml`

**蟇ｾ蠢・*:
```
繝偵Φ繝・ 蜈医↓ 'uv run postgres_generate' 繧貞ｮ溯｡後＠縺ｦ縺上□縺輔＞
```

### 3. 繧ｵ繝ｼ繝薙せ襍ｷ蜍輔ち繧､繝繧｢繧ｦ繝・

**繧ｨ繝ｩ繝ｼ**: `TimeoutError: PostgreSQL did not start within 30 seconds`

**蟇ｾ蠢・*:
- 繝ｭ繝ｼ繧ｫ繝ｫ迺ｰ蠅・・諤ｧ閭ｽ遒ｺ隱搾ｼ・PU/繝｡繝｢繝ｪ・・
- Docker 繧､繝｡繝ｼ繧ｸ縺ｮ繝励Ν迥ｶ豕∫｢ｺ隱・
- 繝ｭ繧ｰ遒ｺ隱・ `docker logs <container_name>`

---

## 螳溯｣・ｾ・

### Full Lifecycle (逕滓・ 竊・襍ｷ蜍・竊・蛛懈ｭ｢ 竊・蜑企勁)

```python
from pathlib import Path
from repom.config import RepomConfig
from repom.postgres.manage import PostgresManager

# 險ｭ螳壹ｒ隱ｭ縺ｿ霎ｼ縺ｿ
config = RepomConfig()

# Manager 繧貞・譛溷喧
manager = PostgresManager(config)

try:
    # 1. Docker image 繧偵ン繝ｫ繝会ｼ・ostgreSQL 縺ｮ蝣ｴ蜷茨ｼ・
    # manager.generate()  # TODO: Phase 2 縺ｧ螳溯｣・
    
    # 2. 繧ｳ繝ｳ繝・リ繧定ｵｷ蜍・
    print("逃 Starting PostgreSQL...")
    manager.start()
    
    # 3. 迥ｶ諷狗｢ｺ隱・
    if manager.is_running():
        print("笨・PostgreSQL is ready")
        
        # ... 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ蜃ｦ逅・...
    
    # 4. 蛛懈ｭ｢
    print("竢ｹ Stopping PostgreSQL...")
    manager.stop()
    
except SystemExit as e:
    print(f"笶・Error: {e}")
    sys.exit(1)

finally:
    # 5. 繧ｯ繝ｪ繝ｼ繝ｳ繧｢繝・・・医が繝励す繝ｧ繝ｳ・・
    # manager.remove()
    pass
```

### CLI 縺九ｉ縺ｮ菴ｿ逕ｨ

```bash
# 襍ｷ蜍・
uv run postgres_start

# 蛛懈ｭ｢
uv run postgres_stop

# 蜑企勁
uv run postgres_remove

# 繧ｹ繝・・繧ｿ繧ｹ遒ｺ隱・
uv run postgres_status
```

---

## FAQ

**Q: `wait_for_service()` 縺ｮ `max_retries` 縺ｯ縺ｩ縺ｮ遞句ｺｦ縺悟ｦ･蠖難ｼ・*

A: 繝・ヵ繧ｩ繝ｫ繝医・ 30 遘偵〒縲√⊇縺ｨ繧薙←縺ｮ繧ｵ繝ｼ繝薙せ縺ｫ蜊∝・縺ｧ縺吶・
- 鬮倬・PC: 5-10 遘・
- 騾壼ｸｸ PC: 20-30 遘・
- 驕・＞ PC / CI: 60 遘・

**Q: 隍・焚縺ｮ繧ｵ繝ｼ繝薙せ繧貞酔譎ゅ↓邂｡逅・〒縺阪ｋ・・*

A: 迴ｾ蝨ｨ縺ｮ繧ｳ繝ｼ繝峨・ 1 service 縺・1 manager 縺ｧ縺吶・
蟆・擂縺ｮ諡｡蠑ｵ:
```python
class ServiceGroup:
    def add_service(self, name, manager):
        ...
    
    def start_all(self):
        ...
```

**Q: Docker Compose 繝輔ぃ繧､繝ｫ縺ｮ繧ｫ繧ｹ繧ｿ繝槭う繧ｺ縺ｯ・・*

A: `get_compose_file_path()` 縺ｧ縺ｯ莉ｻ諢上・繝代せ繧定ｿ斐○縺ｾ縺吶・

```python
def get_compose_file_path(self) -> Path:
    env = os.getenv("COMPOSE_ENV", "dev")
    return self.get_compose_dir() / f"docker-compose.{env}.yml"
```

---

## 髢｢騾｣繝峨く繝･繝｡繝ｳ繝・

- [Docker Manager Phase 1 implementation guide](../../technical/docker_manager_phase1_implementation_guide.md)
- [Docker Manager code reduction analysis](../../technical/docker_manager_code_reduction_analysis.md)

---

**譛邨よ峩譁ｰ**: 2026-02-23

