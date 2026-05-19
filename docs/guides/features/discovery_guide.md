# Generic Package Discovery Infrastructure Guide

**basekit.discovery** 縺ｯ縲√ヵ繝ｬ繝ｼ繝繝ｯ繝ｼ繧ｯ髱樔ｾ晏ｭ倥・豎守畑逧・↑繝代ャ繧ｱ繝ｼ繧ｸ繝・ぅ繧ｹ繧ｫ繝舌Μ繝ｼ繝ｻ繧､繝ｳ繝昴・繝医す繧ｹ繝・Β縺ｧ縺吶・

## 搭 逶ｮ谺｡

- [讎りｦ‐(#讎りｦ・
- [蝓ｺ譛ｬ讖溯・](#蝓ｺ譛ｬ讖溯・)
- [荳ｻ隕√↑髢｢謨ｰ](#荳ｻ隕√↑髢｢謨ｰ)
- [菴ｿ逕ｨ萓犠(#菴ｿ逕ｨ萓・
- [繝ｦ繝ｼ繧ｹ繧ｱ繝ｼ繧ｹ](#繝ｦ繝ｼ繧ｹ繧ｱ繝ｼ繧ｹ)
- [繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ](#繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ)
- [繧ｻ繧ｭ繝･繝ｪ繝・ぅ](#繧ｻ繧ｭ繝･繝ｪ繝・ぅ)
- [繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ](#繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ)

---

## 讎りｦ・

### 迚ｹ蠕ｴ

- **繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ髱樔ｾ晏ｭ・*: SQLAlchemy 縺ｫ髯仙ｮ壹＆繧後★縲√≠繧峨ｆ繧・Python 繝代ャ繧ｱ繝ｼ繧ｸ縺ｧ菴ｿ逕ｨ蜿ｯ閭ｽ
- **讒矩蛹悶＆繧後◆繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ**: 螟ｱ謨玲ュ蝣ｱ繧・`DiscoveryFailure` 縺ｨ縺励※霑泌唆
- **繧ｻ繧ｭ繝･繝ｪ繝・ぅ讀懆ｨｼ**: 繝帙Ρ繧､繝医Μ繧ｹ繝域婿蠑上〒繧､繝ｳ繝昴・繝亥ｯｾ雎｡繧貞宛髯・
- **譟碑ｻ溘↑繝輔ャ繧ｯ讖滓ｧ・*: 繧､繝ｳ繝昴・繝亥ｮ御ｺ・ｾ後↓莉ｻ諢上・蜃ｦ逅・ｒ螳溯｡悟庄閭ｽ

### 繝ｦ繝ｼ繧ｹ繧ｱ繝ｼ繧ｹ

- **SQLAlchemy 繝｢繝・Ν**: repom.models 閾ｪ蜍輔う繝ｳ繝昴・繝・
- **FastAPI 繝ｫ繝ｼ繧ｿ繝ｼ**: app/routes 繝・ぅ繝ｬ繧ｯ繝医Μ縺九ｉ閾ｪ蜍慕匳骭ｲ
- **Celery 繧ｿ繧ｹ繧ｯ**: tasks 繝・ぅ繝ｬ繧ｯ繝医Μ縺九ｉ閾ｪ蜍墓､懷・
- **繝励Λ繧ｰ繧､繝ｳ 繧ｷ繧ｹ繝・Β**: plugins 繝・ぅ繝ｬ繧ｯ繝医Μ縺九ｉ蜍慕噪繝ｭ繝ｼ繝・

---

## 蝓ｺ譛ｬ讖溯・

### 1. 繝代せ豁｣隕丞喧

譁・ｭ怜・縲√Μ繧ｹ繝医√き繝ｳ繝槫玄蛻・ｊ譁・ｭ怜・繧堤ｵｱ荳逧・↓謇ｱ縺・∪縺吶・

```python
from basekit.discovery import normalize_paths

# 繧ｫ繝ｳ繝槫玄蛻・ｊ譁・ｭ怜・
paths = normalize_paths("app.routes,app.api,app.tasks")
# ['app.routes', 'app.api', 'app.tasks']

# 繝ｪ繧ｹ繝・
paths = normalize_paths(["app.routes", "app.api"])
# ['app.routes', 'app.api']

# None・育ｩｺ繝ｪ繧ｹ繝茨ｼ・
paths = normalize_paths(None)
# []
```

### 2. 讒矩蛹悶お繝ｩ繝ｼ

螟ｱ謨玲ュ蝣ｱ繧・`DiscoveryFailure` 縺ｨ縺励※霑泌唆縺励∪縺吶・

```python
from basekit.discovery import DiscoveryFailure

failure = DiscoveryFailure(
    target="myapp.nonexistent",
    target_type="package",
    exception_type="ModuleNotFoundError",
    message="No module named 'myapp.nonexistent'"
)

# 霎樊嶌蠖｢蠑上〒蜿門ｾ・
print(failure.to_dict())
# {
#     'target': 'myapp.nonexistent',
#     'target_type': 'package',
#     'exception_type': 'ModuleNotFoundError',
#     'message': "No module named 'myapp.nonexistent'"
# }
```

### 3. 繧ｻ繧ｭ繝･繝ｪ繝・ぅ讀懆ｨｼ

繝帙Ρ繧､繝医Μ繧ｹ繝域婿蠑上〒菫｡鬆ｼ縺ｧ縺阪ｋ繝代ャ繧ｱ繝ｼ繧ｸ縺ｮ縺ｿ繧偵う繝ｳ繝昴・繝医・

```python
from basekit.discovery import validate_package_security

# 險ｱ蜿ｯ縺輔ｌ縺溘・繝ｬ繝輔ぅ繝・け繧ｹ
allowed = {'myapp.', 'shared.', 'repom.'}

# OK
validate_package_security('myapp.routes', allowed)

# NG: ValueError 縺檎匱逕・
validate_package_security('untrusted.package', allowed)
```

---

## 荳ｻ隕√↑髢｢謨ｰ

### import_packages()

**逕ｨ騾・*: 隍・焚縺ｮ繝代ャ繧ｱ繝ｼ繧ｸ繧剃ｸ諡ｬ繧､繝ｳ繝昴・繝茨ｼ域ｵ・＞繧､繝ｳ繝昴・繝茨ｼ・

```python
from basekit.discovery import import_packages

# 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿
failures = import_packages(['myapp.routes', 'myapp.tasks'])
if failures:
    for f in failures:
        print(f"Failed: {f.target} - {f.message}")

# 繧ｻ繧ｭ繝･繝ｪ繝・ぅ讀懆ｨｼ莉倥″
failures = import_packages(
    'myapp.routes,myapp.tasks',
    allowed_prefixes={'myapp.', 'shared.'}
)

# 繧ｨ繝ｩ繝ｼ譎ゅ↓萓句､悶ｒ逋ｺ逕・
from basekit.discovery import DiscoveryError

try:
    import_packages(['nonexistent.package'], fail_on_error=True)
except DiscoveryError as e:
    print(f"Failed: {len(e.failures)} packages")
```

**迚ｹ蠕ｴ**:
- 繝代ャ繧ｱ繝ｼ繧ｸ縺ｮ繝医ャ繝励Ξ繝吶Ν縺ｮ縺ｿ繧偵う繝ｳ繝昴・繝・
- 繧ｵ繝悶Δ繧ｸ繝･繝ｼ繝ｫ縺ｯ閾ｪ蜍慕噪縺ｫ繧､繝ｳ繝昴・繝医＆繧後↑縺・
- 霆ｽ驥上〒鬮倬・

---

### import_from_directory()

**逕ｨ騾・*: 繝・ぅ繝ｬ繧ｯ繝医Μ蜀・・ Python 繝輔ぃ繧､繝ｫ繧貞・蟶ｰ逧・↓繧､繝ｳ繝昴・繝・

```python
from pathlib import Path
from basekit.discovery import import_from_directory

# 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿
failures = import_from_directory(
    directory=Path("src/myapp/routes"),
    base_package="myapp.routes"
)

# 髯､螟悶ョ繧｣繝ｬ繧ｯ繝医Μ繧呈欠螳・
failures = import_from_directory(
    directory="src/myapp/models",
    base_package="myapp.models",
    excluded_dirs={'base', 'utils', 'helpers', '__pycache__'}
)

# 繧ｨ繝ｩ繝ｼ譎ゅ↓萓句､悶ｒ逋ｺ逕・
failures = import_from_directory(
    directory="src/myapp/tasks",
    base_package="myapp.tasks",
    fail_on_error=True
)
```

**迚ｹ蠕ｴ**:
- 繝・ぅ繝ｬ繧ｯ繝医Μ繧貞・蟶ｰ逧・↓襍ｰ譟ｻ
- `.py` 繝輔ぃ繧､繝ｫ繧定・蜍墓､懷・縺励※繧､繝ｳ繝昴・繝・
- `__init__.py` 繧・`_private.py` 縺ｯ繧ｹ繧ｭ繝・・
- 繧｢繝ｫ繝輔ぃ繝吶ャ繝磯・↓遒ｺ螳溘↓繧､繝ｳ繝昴・繝・
- 髯､螟悶ョ繧｣繝ｬ繧ｯ繝医Μ繧呈欠螳壼庄閭ｽ・医ョ繝輔か繝ｫ繝・ `{'__pycache__'}`・・

**繧､繝ｳ繝昴・繝磯・ｺ・*:
```
myapp/routes/
笏懌楳笏 __init__.py          # 繧ｹ繧ｭ繝・・
笏懌楳笏 _internal.py         # 繧ｹ繧ｭ繝・・・・縺ｧ蟋九∪繧具ｼ・
笏懌楳笏 admin.py             # 1. 繧､繝ｳ繝昴・繝・
笏懌楳笏 api.py               # 2. 繧､繝ｳ繝昴・繝・
笏披楳笏 users/
    笏懌楳笏 __init__.py      # 繧ｹ繧ｭ繝・・
    笏懌楳笏 auth.py          # 3. 繧､繝ｳ繝昴・繝・(myapp.routes.users.auth)
    笏披楳笏 profile.py       # 4. 繧､繝ｳ繝昴・繝・(myapp.routes.users.profile)
```

---

### import_package_directory()

**逕ｨ騾・*: 繝代ャ繧ｱ繝ｼ繧ｸ蜷阪ｒ謖・ｮ壹＠縺ｦ繝・ぅ繝ｬ繧ｯ繝医Μ繧定・蜍墓､懷・縺励∝・蟶ｰ逧・↓繧､繝ｳ繝昴・繝・

```python
from basekit.discovery import import_package_directory

# 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿
failures = import_package_directory('myapp.models')

# 繧ｻ繧ｭ繝･繝ｪ繝・ぅ讀懆ｨｼ莉倥″
failures = import_package_directory(
    'myapp.routes',
    allowed_prefixes={'myapp.', 'shared.', 'repom.'}
)

# 髯､螟悶ョ繧｣繝ｬ繧ｯ繝医Μ繧呈欠螳・
failures = import_package_directory(
    'myapp.models',
    excluded_dirs={'base', 'mixin', 'tests'}
)
```

**迚ｹ蠕ｴ**:
- 繝代ャ繧ｱ繝ｼ繧ｸ蜷阪°繧峨ョ繧｣繝ｬ繧ｯ繝医Μ繧定・蜍募叙蠕・
- `import_from_directory()` 繧貞・驛ｨ縺ｧ菴ｿ逕ｨ
- 繝代ャ繧ｱ繝ｼ繧ｸ縺悟ｭ伜惠縺励↑縺・ｴ蜷医・ `DiscoveryFailure` 繧定ｿ泌唆

---

### import_from_packages()

**逕ｨ騾・*: 隍・焚縺ｮ繝代ャ繧ｱ繝ｼ繧ｸ繧剃ｸ諡ｬ繧､繝ｳ繝昴・繝・+ 繧､繝ｳ繝昴・繝亥ｮ御ｺ・ｾ後・繝輔ャ繧ｯ螳溯｡・

```python
from basekit.discovery import import_from_packages
from sqlalchemy.orm import configure_mappers

# 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿
failures = import_from_packages([
    'myapp.routes',
    'myapp.tasks'
])

# 繝輔ャ繧ｯ莉倥″・・QLAlchemy 繝｢繝・Ν逕ｨ・・
failures = import_from_packages(
    package_names=['myapp.models', 'shared.models'],
    post_import_hook=configure_mappers  # 縺吶∋縺ｦ縺ｮ繧､繝ｳ繝昴・繝亥ｮ御ｺ・ｾ後↓螳溯｡・
)

# 繧ｫ繝ｳ繝槫玄蛻・ｊ譁・ｭ怜・縺ｧ繧ょ庄
failures = import_from_packages(
    'myapp.routes,myapp.api,myapp.tasks',
    allowed_prefixes={'myapp.'},
    fail_on_error=False
)
```

**迚ｹ蠕ｴ**:
- 隍・焚繝代ャ繧ｱ繝ｼ繧ｸ繧剃ｸ諡ｬ蜃ｦ逅・
- `post_import_hook` 縺ｧ繧､繝ｳ繝昴・繝亥ｮ御ｺ・ｾ後・蜃ｦ逅・ｒ螳溯｡・
- SQLAlchemy 縺ｮ `configure_mappers()` 縺ｨ縺ｮ逶ｸ諤ｧ縺瑚憶縺・
- 蠕ｪ迺ｰ蜿ら・蝠城｡後・隗｣豎ｺ縺ｫ譛牙柑

---

## 菴ｿ逕ｨ萓・

### 萓・: FastAPI 繝ｫ繝ｼ繧ｿ繝ｼ閾ｪ蜍慕匳骭ｲ

```python
# app/main.py
from fastapi import FastAPI
from basekit.discovery import import_from_directory
from pathlib import Path

app = FastAPI()

# 繝ｫ繝ｼ繧ｿ繝ｼ繧定・蜍輔う繝ｳ繝昴・繝・
failures = import_from_directory(
    directory=Path(__file__).parent / "routes",
    base_package="app.routes",
    excluded_dirs={'__pycache__', 'tests'}
)

if failures:
    for f in failures:
        print(f"Warning: Failed to import {f.target}: {f.message}")
```

```python
# app/routes/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def list_users():
    return {"users": []}
```

### 萓・: Celery 繧ｿ繧ｹ繧ｯ閾ｪ蜍慕匳骭ｲ

```python
# celery_app.py
from celery import Celery
from basekit.discovery import import_from_directory
from pathlib import Path

app = Celery('myapp')

# 繧ｿ繧ｹ繧ｯ繧定・蜍輔う繝ｳ繝昴・繝・
failures = import_from_directory(
    directory=Path(__file__).parent / "tasks",
    base_package="myapp.tasks"
)

if failures:
    print(f"Failed to import {len(failures)} tasks")
```

```python
# tasks/email.py
from celery_app import app

@app.task
def send_email(to: str, subject: str):
    print(f"Sending email to {to}")
```

### 萓・: SQLAlchemy 繝｢繝・Ν荳諡ｬ繧､繝ｳ繝昴・繝茨ｼ亥ｾｪ迺ｰ蜿ら・蟇ｾ蠢懶ｼ・

```python
# models/__init__.py
from basekit.discovery import import_from_packages
from sqlalchemy.orm import configure_mappers

def load_all_models():
    """縺吶∋縺ｦ縺ｮ繝｢繝・Ν繧偵う繝ｳ繝昴・繝亥ｾ後√・繝・ヱ繝ｼ繧貞・譛溷喧"""
    failures = import_from_packages(
        package_names=['myapp.models', 'shared.models'],
        excluded_dirs={'base', 'mixin'},
        allowed_prefixes={'myapp.', 'shared.'},
        post_import_hook=configure_mappers  # 蠕ｪ迺ｰ蜿ら・繧定ｧ｣豎ｺ
    )
    
    if failures:
        for f in failures:
            print(f"Warning: {f.target} - {f.message}")
    
    return failures
```

### 萓・: 繝励Λ繧ｰ繧､繝ｳ繧ｷ繧ｹ繝・Β

```python
# plugins/loader.py
from basekit.discovery import import_from_directory
from pathlib import Path

class PluginManager:
    def __init__(self):
        self.plugins = []
    
    def load_plugins(self, plugin_dir: Path):
        """繝励Λ繧ｰ繧､繝ｳ繧貞虚逧・↓繝ｭ繝ｼ繝・""
        failures = import_from_directory(
            directory=plugin_dir,
            base_package="plugins",
            fail_on_error=False
        )
        
        if failures:
            for f in failures:
                print(f"Plugin load failed: {f.target}")
        
        # 繝ｭ繝ｼ繝峨＆繧後◆繝励Λ繧ｰ繧､繝ｳ繧貞庶髮・
        import sys
        for name, module in sys.modules.items():
            if name.startswith('plugins.') and hasattr(module, 'Plugin'):
                self.plugins.append(module.Plugin())
        
        return len(self.plugins)

# 菴ｿ逕ｨ萓・
manager = PluginManager()
count = manager.load_plugins(Path("plugins"))
print(f"Loaded {count} plugins")
```

---

## 繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ

### fail_on_error=False・医ョ繝輔か繝ｫ繝茨ｼ・

螟ｱ謨玲ュ蝣ｱ繧・`DiscoveryFailure` 縺ｮ繝ｪ繧ｹ繝医→縺励※霑泌唆縺励∪縺吶・

```python
failures = import_from_packages(['myapp.routes', 'nonexistent.package'])

# 螟ｱ謨励＠縺溷ｯｾ雎｡繧堤｢ｺ隱・
for failure in failures:
    print(f"Target: {failure.target}")
    print(f"Type: {failure.target_type}")
    print(f"Error: {failure.exception_type} - {failure.message}")
```

### fail_on_error=True

譛蛻昴・螟ｱ謨励〒 `DiscoveryError` 繧堤匱逕溘＆縺帙∪縺吶・

```python
from basekit.discovery import DiscoveryError

try:
    import_from_packages(
        ['myapp.routes', 'nonexistent.package'],
        fail_on_error=True
    )
except DiscoveryError as e:
    print(f"Discovery failed with {len(e.failures)} error(s)")
    for failure in e.failures:
        print(f"  - {failure.target}: {failure.message}")
```

### 繝ｭ繧ｰ蜃ｺ蜉・

```python
import logging
from basekit.discovery import import_from_packages

logging.basicConfig(level=logging.INFO)

failures = import_from_packages(['myapp.routes'])

if failures:
    logger = logging.getLogger(__name__)
    for f in failures:
        logger.error(
            "Import failed",
            extra=f.to_dict()  # 讒矩蛹悶Ο繧ｰ
        )
```

---

## 繧ｻ繧ｭ繝･繝ｪ繝・ぅ

### 繝帙Ρ繧､繝医Μ繧ｹ繝域婿蠑・

菫｡鬆ｼ縺ｧ縺阪ｋ繝代ャ繧ｱ繝ｼ繧ｸ繝励Ξ繝輔ぅ繝・け繧ｹ縺ｮ縺ｿ繧定ｨｱ蜿ｯ縺励∪縺吶・

```python
from basekit.discovery import import_from_packages

# 險ｱ蜿ｯ縺輔ｌ縺溘・繝ｬ繝輔ぅ繝・け繧ｹ
ALLOWED_PREFIXES = {
    'myapp.',      # 閾ｪ遉ｾ繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ
    'shared.',     # 蜈ｱ譛峨Λ繧､繝悶Λ繝ｪ
    'plugins.',    # 蜈ｬ蠑上・繝ｩ繧ｰ繧､繝ｳ
    'repom.'       # repom 閾ｪ菴・
}

# 繧ｻ繧ｭ繝･繝ｪ繝・ぅ讀懆ｨｼ莉倥″繧､繝ｳ繝昴・繝・
failures = import_from_packages(
    ['myapp.routes', 'shared.utils'],
    allowed_prefixes=ALLOWED_PREFIXES
)

# untrusted.package 縺ｯ繧､繝ｳ繝昴・繝域凾縺ｫ ValueError 縺檎匱逕・
try:
    import_from_packages(
        ['untrusted.package'],
        allowed_prefixes=ALLOWED_PREFIXES
    )
except ValueError as e:
    print(f"Security violation: {e}")
```

### 謗ｨ螂ｨ莠矩・

1. **蟶ｸ縺ｫ allowed_prefixes 繧定ｨｭ螳・*: 蜍慕噪繧､繝ｳ繝昴・繝医ｒ菴ｿ逕ｨ縺吶ｋ蝣ｴ蜷医・蠢・・
2. **譛蟆乗ｨｩ髯舌・蜴溷援**: 蠢・ｦ∵怙蟆城剞縺ｮ繝励Ξ繝輔ぅ繝・け繧ｹ縺ｮ縺ｿ繧定ｨｱ蜿ｯ
3. **迺ｰ蠅・挨險ｭ螳・*: 髢狗匱迺ｰ蠅・→譛ｬ逡ｪ迺ｰ蠅・〒逡ｰ縺ｪ繧玖ｨｭ螳壹ｒ菴ｿ逕ｨ

```python
# config.py
import os

def get_allowed_prefixes():
    if os.getenv('ENV') == 'production':
        return {'myapp.', 'shared.'}
    else:
        return {'myapp.', 'shared.', 'test.', 'debug.'}
```

---

## 繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ

### 1. 髯､螟悶ョ繧｣繝ｬ繧ｯ繝医Μ繧呈・遉ｺ逧・↓謖・ｮ・

```python
# Good: 譏守､ｺ逧・↓謖・ｮ・
failures = import_from_directory(
    directory="src/myapp/models",
    base_package="myapp.models",
    excluded_dirs={'base', 'mixin', 'tests', 'migrations', '__pycache__'}
)

# Bad: 繝・ヵ繧ｩ繝ｫ繝医↓鬆ｼ繧具ｼ・_pycache__ 縺ｮ縺ｿ髯､螟厄ｼ・
failures = import_from_directory(
    directory="src/myapp/models",
    base_package="myapp.models"
)
```

### 2. 繝輔ャ繧ｯ繧呈ｴｻ逕ｨ縺励※蠕ｪ迺ｰ蜿ら・繧定ｧ｣豎ｺ

```python
from sqlalchemy.orm import configure_mappers

# Good: 縺吶∋縺ｦ繧､繝ｳ繝昴・繝亥ｾ後↓繝槭ャ繝代・蛻晄悄蛹・
failures = import_from_packages(
    ['myapp.models.user', 'myapp.models.post'],
    post_import_hook=configure_mappers
)

# Bad: 蛟句挨縺ｫ繧､繝ｳ繝昴・繝・+ 蛟句挨縺ｫ蛻晄悄蛹厄ｼ亥ｾｪ迺ｰ蜿ら・繧ｨ繝ｩ繝ｼ・・
import_package_directory('myapp.models.user')
configure_mappers()  # 竊・post 縺後∪縺繧､繝ｳ繝昴・繝医＆繧後※縺・↑縺・
import_package_directory('myapp.models.post')
```

### 3. 繧ｨ繝ｩ繝ｼ繧帝←蛻・↓繝ｭ繧ｰ蜃ｺ蜉・

```python
import logging

logger = logging.getLogger(__name__)

failures = import_from_packages(['myapp.routes'])

if failures:
    for f in failures:
        if f.exception_type == 'ModuleNotFoundError':
            logger.warning(f"Optional module not found: {f.target}")
        else:
            logger.error(f"Import failed: {f.target} - {f.message}")
```

### 4. 繝・せ繝育腸蠅・〒縺ｮ豕ｨ諢冗せ

```python
# 繝・せ繝亥燕縺ｫ繝｢繧ｸ繝･繝ｼ繝ｫ繧ｭ繝｣繝・す繝･繧偵け繝ｪ繧｢
import sys

def clean_module_cache(prefix: str):
    """謖・ｮ壹・繝ｬ繝輔ぅ繝・け繧ｹ縺ｮ繝｢繧ｸ繝･繝ｼ繝ｫ繧偵く繝｣繝・す繝･縺九ｉ蜑企勁"""
    for key in list(sys.modules.keys()):
        if key.startswith(prefix):
            del sys.modules[key]

# 繝・せ繝・
def test_import():
    clean_module_cache('test_app.')
    
    failures = import_from_directory(
        directory="test_app",
        base_package="test_app"
    )
    
    assert len(failures) == 0
```

---

## 豈碑ｼ・ 譌ｧAPI vs 譁ｰAPI

| 譌ｧAPI | 譁ｰAPI | 逕ｨ騾・|
|-------|-------|------|
| `auto_import_models()` | `import_from_directory()` | 繝・ぅ繝ｬ繧ｯ繝医Μ繝吶・繧ｹ |
| `auto_import_models_by_package()` | `import_package_directory()` | 繝代ャ繧ｱ繝ｼ繧ｸ繝吶・繧ｹ |
| `auto_import_models_from_list()` | `import_from_packages()` | 荳諡ｬ繧､繝ｳ繝昴・繝・+ 繝輔ャ繧ｯ |

### 遘ｻ陦御ｾ・

**譌ｧAPI**:
```python
from repom.utility import auto_import_models_from_list
from sqlalchemy.orm import configure_mappers

auto_import_models_from_list(
    package_names=['myapp.models'],
    excluded_dirs={'tests'},
    allowed_prefixes={'myapp.'},
    fail_on_error=False
)
configure_mappers()  # 蛻･騾泌他縺ｳ蜃ｺ縺・
```

**譁ｰAPI**:
```python
from basekit.discovery import import_from_packages
from sqlalchemy.orm import configure_mappers

import_from_packages(
    package_names=['myapp.models'],
    excluded_dirs={'tests'},
    allowed_prefixes={'myapp.'},
    fail_on_error=False,
    post_import_hook=configure_mappers  # 繝輔ャ繧ｯ縺ｧ邨ｱ蜷・
)
```

---

## 縺ｾ縺ｨ繧・

basekit の discovery インフラは、repom のモデル自動インポートを含む次の用途で利用できます。

- 笨・**SQLAlchemy 繝｢繝・Ν**: 蠕ｪ迺ｰ蜿ら・蟇ｾ蠢懊・荳諡ｬ繧､繝ｳ繝昴・繝・
- 笨・**FastAPI 繝ｫ繝ｼ繧ｿ繝ｼ**: 閾ｪ蜍墓､懷・縺ｨ逋ｻ骭ｲ
- 笨・**Celery 繧ｿ繧ｹ繧ｯ**: 繧ｿ繧ｹ繧ｯ縺ｮ蜍慕噪繝ｭ繝ｼ繝・
- 笨・**繝励Λ繧ｰ繧､繝ｳ繧ｷ繧ｹ繝・Β**: 諡｡蠑ｵ讖溯・縺ｮ蜍慕噪隱ｭ縺ｿ霎ｼ縺ｿ
- 笨・**縺昴・莉・*: 縺ゅｉ繧・ｋ Python 繝代ャ繧ｱ繝ｼ繧ｸ縺ｮ閾ｪ蜍輔う繝ｳ繝昴・繝・

**繧ｭ繝ｼ繝昴う繝ｳ繝・*:
1. **讒矩蛹悶＆繧後◆繧ｨ繝ｩ繝ｼ**: `DiscoveryFailure` 縺ｧ螟ｱ謨玲ュ蝣ｱ繧堤ｮ｡逅・
2. **繧ｻ繧ｭ繝･繝ｪ繝・ぅ**: 繝帙Ρ繧､繝医Μ繧ｹ繝域婿蠑上〒螳牙・縺ｫ繧､繝ｳ繝昴・繝・
3. **繝輔ャ繧ｯ讖滓ｧ・*: `post_import_hook` 縺ｧ譟碑ｻ溘↑蜃ｦ逅・ｒ螳溽樟
4. **繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ髱樔ｾ晏ｭ・*: 豎守畑逧・↑險ｭ險医〒蜀榊茜逕ｨ諤ｧ縺碁ｫ倥＞

現行実装は basekit 側の [`src/basekit/discovery.py`](../../../../basekit/src/basekit/discovery.py) を参照してください。repom 側の旧 `repom/_/discovery.py` は削除済みです。

