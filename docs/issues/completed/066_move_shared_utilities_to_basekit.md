**Status**: Completed
**Completed**: 2026-05-19

# Issue #66: `repom/_/` 蜈ｱ譛峨Θ繝ｼ繝・ぅ繝ｪ繝・ぅ繧・basekit 縺ｸ遘ｻ邂｡

**繧ｹ繝・・繧ｿ繧ｹ**: 閥 譛ｪ逹謇・
**菴懈・譌･**: 2026-05-19

**蜆ｪ蜈亥ｺｦ**: 荳ｭ

## 蝠城｡後・隱ｬ譏・
`repom/_/` 驟堺ｸ九・ 3 繝輔ぃ繧､繝ｫ縺ｯ縺・★繧後ｂ繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ髱樔ｾ晏ｭ倥・豎守畑繝ｦ繝ｼ繝・ぅ繝ｪ繝・ぅ縺ｧ縲・repom 蝗ｺ譛峨・讎ょｿｵ・医Δ繝・Ν / 繝ｪ繝昴ず繝医Μ / SQLAlchemy 縺ｪ縺ｩ・峨↓萓晏ｭ倥＠縺ｦ縺・↑縺・・
- [repom/_/discovery.py](../../../repom/_/discovery.py)
  繝代ャ繧ｱ繝ｼ繧ｸ繝ｻ繝｢繧ｸ繝･繝ｼ繝ｫ縺ｮ蜍慕噪繧､繝ｳ繝昴・繝医→螟ｱ謨鈴寔邏・ょ､夜Κ萓晏ｭ倥・讓呎ｺ悶Λ繧､繝悶Λ繝ｪ縺ｮ縺ｿ縲・- [repom/_/docker_compose.py](../../../repom/_/docker_compose.py)
  `DockerService` / `DockerVolume` / `DockerComposeGenerator`縲ょｮ悟・縺ｫ邏皮ｲ九↑繝ｦ繝ｼ繝・ぅ繝ｪ繝・ぅ縲・- [repom/_/docker_manager.py](../../../repom/_/docker_manager.py)
  `DockerCommandExecutor`縲～DockerManager` 蝓ｺ逶､縲～print_message` / `validate_compose_file_exists` / `format_connection_info`縲・  蜚ｯ荳 `from repom.config import config` 縺ｫ萓晏ｭ倥＠縲～config.data_path` 繧・`get_compose_dir()` 縺九ｉ蜿ら・縺励※縺・ｋ縲・
縺薙ｌ繧峨・ basekit・・C:/Users/jj/Desktop/workspace_main/projects/basekit](C:/Users/jj/Desktop/workspace_main/projects/basekit)・峨↓遘ｻ縺吶・縺瑚・辟ｶ縺ｧ縲・basekit 繧剃ｾ晏ｭ倥☆繧倶ｻ悶・繝ｭ繧ｸ繧ｧ繧ｯ繝茨ｼ・ast-domain 縺ｪ縺ｩ・峨〒繧ょ・蛻ｩ逕ｨ縺ｧ縺阪ｋ縲・莠呈鋤諤ｧ邯ｭ謖√・蛻ｶ邏・・縺ｪ縺上（mport 繝代せ繧貞ｮ悟・縺ｫ蛻・ｊ譖ｿ縺医ｋ蜑肴署縺ｧ騾ｲ繧√※繧医＞縲・
## 謠先｡医＆繧後ｋ隗｣豎ｺ遲・
### 遘ｻ邂｡蜈医→蜈ｬ髢・API・・asekit 蛛ｴ・・
basekit 縺ｯ繧ｽ繝ｼ繧ｹ繧・`src/basekit/` 逶ｴ荳九↓繝輔Λ繝・ヨ縺ｫ鄂ｮ縺乗ｧ区・縺ｪ縺ｮ縺ｧ縲√し繝悶ヱ繝・こ繝ｼ繧ｸ繧・1 縺､菴懊ｋ縺ｮ縺ｧ縺ｯ縺ｪ縺・**讖溯・縺斐→縺ｫ繝｢繧ｸ繝･繝ｼ繝ｫ 1 繝輔ぃ繧､繝ｫ** 繧定ｿｽ蜉縺吶ｋ蠖｢縺ｫ謠・∴繧九・
```
src/basekit/
笏懌楳笏 __init__.py
笏懌楳笏 config_hook.py
笏懌楳笏 logging.py
笏懌楳笏 discovery.py       # NEW (= repom/_/discovery.py 繧偵◎縺ｮ縺ｾ縺ｾ遘ｻ讀・
笏懌楳笏 docker_compose.py  # NEW (= repom/_/docker_compose.py 繧偵◎縺ｮ縺ｾ縺ｾ遘ｻ讀・
笏披楳笏 docker_manager.py  # NEW (= repom/_/docker_manager.py 繧貞・險ｭ險医＠縺ｦ遘ｻ讀・
```

import 邨瑚ｷｯ縺ｯ・・
```python
from basekit.discovery import import_from_packages, DiscoveryError, ...
from basekit.docker_compose import DockerComposeGenerator, DockerService, DockerVolume
from basekit.docker_manager import (
    DockerManager,
    DockerCommandExecutor,
    print_message,
    validate_compose_file_exists,
    format_connection_info,
)
```

### 繝｢繧ｸ繝･繝ｼ繝ｫ蛻･縺ｮ險ｭ險域婿驥・
#### 1. `basekit.discovery`・育┌螟画峩遘ｻ讀搾ｼ・
- 迴ｾ迥ｶ縺ｮ API・・normalize_paths` / `DiscoveryFailure` / `DiscoveryError` /
  `validate_package_security` / `import_packages` / `import_from_directory` /
  `import_package_directory` / `import_from_packages`・峨ｒ縺昴・縺ｾ縺ｾ遘ｻ縺吶・- 螟夜Κ萓晏ｭ倥↑縺励ゅユ繧ｹ繝医ｂ `tests/unit_tests/test_discovery_helpers.py` 繧・basekit 蛛ｴ縺ｸ遘ｻ讀榊庄閭ｽ縲・
#### 2. `basekit.docker_compose`・育┌螟画峩遘ｻ讀搾ｼ・
- `DockerService` / `DockerVolume` / `DockerComposeGenerator` 繧偵◎縺ｮ縺ｾ縺ｾ遘ｻ縺吶・- 蜊倅ｽ薙ユ繧ｹ繝・`tests/unit_tests/test_docker_compose.py` 繧・basekit 縺ｸ遘ｻ讀阪・
#### 3. `basekit.docker_manager`・・*蜀崎ｨｭ險医′蠢・ｦ・*・・
迴ｾ迥ｶ縺ｮ `DockerManager` 縺ｯ `from repom.config import config` 繧偵Δ繧ｸ繝･繝ｼ繝ｫ繝医ャ繝励〒 import 縺励・`get_compose_dir()` 蜀・〒 `Path(config.data_path) / self.SERVICE_NAME` 繧堤ｵ・∩遶九※縺ｦ縺・ｋ縲・basekit 縺ｫ縺ｯ repom 縺ｸ縺ｮ蜿ら・繧呈戟縺溘○縺ｪ縺・◆繧√√％縺薙ｒ險ｭ螳壽ｳｨ蜈･・・I・画婿蠑上↓螟峨∴繧九・
**螟画峩轤ｹ (A): `repom.config` 縺ｸ縺ｮ萓晏ｭ倥ｒ蛻・ｋ**

[repom/_/docker_manager.py:30](../../../repom/_/docker_manager.py#L30) 縺ｮ繝｢繧ｸ繝･繝ｼ繝ｫ繝ｬ繝吶Ν import 繧貞ｻ・ｭ｢縺励・`DockerManager.__init__` 縺ｧ `data_path` 繧貞女縺大叙繧具ｼ医∪縺溘・ `basekit.Config` 繧貞女縺大叙繧具ｼ峨・
```python
# basekit/docker_manager.py
from basekit.config_hook import Config

class DockerManager(ABC):
    SERVICE_NAME: ClassVar[str]
    INIT_SUBDIR: ClassVar[str]
    GENERATE_COMMAND: ClassVar[str]

    def __init__(self, *, data_path: str | Path, ...):
        self._data_path = Path(data_path)

    def get_compose_dir(self) -> Path:
        compose_dir = self._data_path / self.SERVICE_NAME
        compose_dir.mkdir(parents=True, exist_ok=True)
        return compose_dir
```

repom 蛛ｴ縺ｮ繧ｵ繝悶け繝ｩ繧ｹ縺ｯ `super().__init__(data_path=config.data_path)` 繧貞他縺ｶ蠖｢縺ｫ螟峨∴繧九・・・epom 縺ｮ `RepomConfig` 縺ｯ basekit 縺ｮ `Config` 繧堤ｶ呎価縺励※縺・ｋ縺ｮ縺ｧ `data_path` 繝励Ο繝代ユ繧｣縺ｯ蛻ｩ逕ｨ蜿ｯ閭ｽ縲ゑｼ・
**螟画峩轤ｹ (B): `GENERATE_COMMAND` 縺ｮ繝偵Φ繝域枚險繧呈歓雎｡蛹・*

迴ｾ迥ｶ `get_compose_file_path()` 縺ｮ繧ｨ繝ｩ繝ｼ繝｡繝・そ繝ｼ繧ｸ縺ｯ
`"Hint: Run 'uv run {self.GENERATE_COMMAND}' first"` 縺ｨ repom 縺ｮ CLI 蜻ｽ蜷榊燕謠舌・繝輔か繝ｼ繝槭ャ繝医↓縺ｪ縺｣縺ｦ縺・ｋ縲・basekit 縺ｫ鄂ｮ縺丈ｻ･荳翫～uv run` 蝗ｺ螳壹・繧・ａ縺ｦ繧ｵ繝悶け繝ｩ繧ｹ蛛ｴ縺ｧ閾ｪ逕ｱ縺ｫ荳頑嶌縺阪〒縺阪ｋ繧医≧縲・繧ｯ繝ｩ繧ｹ螟画焚 `GENERATE_COMMAND_HINT` 繧貞挨騾泌・繧雁・縺吶°縲～hint_message` 繝｡繧ｽ繝・ラ縺ｫ蛻・屬縺吶ｋ縲・
```python
class DockerManager(ABC):
    GENERATE_COMMAND: ClassVar[str]

    def get_generate_hint(self) -> str:
        return f"Hint: Run 'uv run {self.GENERATE_COMMAND}' first"
```

repom 蛛ｴ繧ｵ繝悶け繝ｩ繧ｹ縺ｯ譌｢螳壼ｮ溯｣・ｒ菴ｿ縺・□縺代〒迴ｾ迥ｶ縺ｨ遲我ｾ｡縲Ｇast-domain 縺ｪ縺ｩ莉悶・繝ｭ繧ｸ繧ｧ繧ｯ繝医〒縺ｯ
繧ｪ繝ｼ繝舌・繝ｩ繧､繝峨〒縺阪ｋ菴吝慍繧呈ｮ九☆縲・
**螟画峩轤ｹ (C): 繝｡繝・そ繝ｼ繧ｸ譁・ｨ縺ｮ闍ｱ隱槫喧・郁ｻｽ蠕ｮ・・*

`validate_compose_file_exists()` 縺ｮ荳ｭ縺ｫ譌･譛ｬ隱樊枚蟄怜・
・・docker-compose.generated.yml 縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ" / "蜈医↓ '...' 繧貞ｮ溯｡後＠縺ｦ縺上□縺輔＞"・峨′豺ｷ縺悶▲縺ｦ縺・ｋ縲・basekit 縺ｯ豎守畑繝代ャ繧ｱ繝ｼ繧ｸ縺ｪ縺ｮ縺ｧ闍ｱ隱槭↓謠・∴繧具ｼ域里蟄倥ぎ繧､繝峨・蜥瑚ｨｳ縺ｯ repom 蛛ｴ繧ｬ繧､繝峨↓谿九☆・峨・
**螟画峩轤ｹ (D): `print_message` 縺ｮ邨ｵ譁・ｭ励ヵ繧ｩ繝ｼ繝ｫ繝舌ャ繧ｯ・亥､画峩縺ｪ縺暦ｼ・*

cp932 蟇ｾ遲悶・ `try / except UnicodeEncodeError` 蛻・ｲ舌・ basekit 縺ｧ繧ゅ◎縺ｮ縺ｾ縺ｾ謗｡逕ｨ縺吶ｋ縲・
### repom 蛛ｴ縺ｮ蟾ｮ縺玲崛縺井ｽ懈･ｭ

莠呈鋤繧ｷ繝縺ｯ險ｭ縺代★縲～from repom._.X` 竊・`from basekit.X` 縺ｫ荳諡ｬ鄂ｮ謠帙＠縲・`repom/_/discovery.py` / `repom/_/docker_compose.py` / `repom/_/docker_manager.py` 繧貞炎髯､縺吶ｋ縲・`repom/_/__init__.py` 繧ゆｻ悶↓蜀・ｮｹ縺後↑縺代ｌ縺ｰ蜑企勁縺吶ｋ・郁ｦ∫｢ｺ隱搾ｼ峨・
蟾ｮ縺玲崛縺亥ｯｾ雎｡・・rep 譌｢隱ｿ譟ｻ貂茨ｼ・

- `repom/utility.py:7-17`・・iscovery・・- `repom/postgres/manage.py:14-15`・・ocker_compose, docker_manager・・- `repom/redis/manage.py:14-15`・亥酔荳奇ｼ・- `repom/scripts/repom_info.py`
- `repom/scripts/db_backup.py`
- `repom/scripts/db_restore.py`
- `tests/unit_tests/test_auto_import_models.py`
- `tests/unit_tests/test_discovery_helpers.py`
- `tests/unit_tests/test_docker_compose.py`
- `tests/unit_tests/test_redis_manager.py`
- `tests/unit_tests/docker_manager/` 驟堺ｸ・4 繝輔ぃ繧､繝ｫ
- `tests/behavior_tests/test_type_checking_import_order.py`
- `tests/behavior_tests/test_type_checking_detailed.py`
- `tests/behavior_tests/test_circular_import.py`
- `tests/behavior_tests/test_circular_import_solutions.py`

縺ｪ縺・`repom/_/docker_manager.py:339` 縺ｮ `get_compose_file_path()` 縺ｯ basekit 縺ｫ遘ｻ縺｣縺溘≠縺ｨ縲・repom 蛛ｴ `PostgresManager` / `RedisManager` 縺ｫ `data_path` 繧呈ｸ｡縺吶さ繝ｳ繧ｹ繝医Λ繧ｯ繧ｿ螟画峩縺悟ｿ・ｦ√↓縺ｪ繧九・
### 繧ｬ繧､繝峨・蟾ｮ縺玲崛縺・
- [docs/guides/features/discovery_guide.md](../../guides/features/discovery_guide.md)
- [docs/guides/features/docker_compose_guide.md](../../guides/features/docker_compose_guide.md)
- [docs/guides/features/docker_manager_guide.md](../../guides/features/docker_manager_guide.md)

縺薙ｌ繧峨・ import 萓九ｒ `basekit.X` 邉ｻ縺ｫ譖ｸ縺肴鋤縺医ｋ縲Ｃasekit 繝ｪ繝昴ず繝医Μ縺ｫ繧ゅぎ繧､繝峨ｒ遘ｻ讀阪☆繧九°縺ｯ
蛻･騾疲､懆ｨ趣ｼ域怙蟆上〒縺ｯ repom 蛛ｴ縺ｧ `basekit 縺ｫ遘ｻ邂｡縺輔ｌ縺歔 譌ｨ縺縺題ｿｽ險倥＠縲∵悽菴薙・ basekit 縺ｫ鄂ｮ縺擾ｼ峨・
### basekit 蛛ｴ縺ｮ繝・せ繝・
repom 蛛ｴ縺ｮ繝・せ繝医・縺・■邏皮ｲ九↑蜊倅ｽ薙ユ繧ｹ繝医・ basekit 縺ｫ遘ｻ讀阪☆繧具ｼ・
- `tests/unit_tests/test_discovery_helpers.py` 竊・basekit `tests/unit_tests/test_discovery.py`
- `tests/unit_tests/test_docker_compose.py` 竊・basekit `tests/unit_tests/test_docker_compose.py`
- `tests/unit_tests/docker_manager/test_docker_command_executor.py`
- `tests/unit_tests/docker_manager/test_utility_functions.py`
- `tests/unit_tests/docker_manager/test_docker_manager.py`・・config` 萓晏ｭ倩ｧ｣豸医↓莨ｴ縺・嶌縺肴鋤縺医≠繧奇ｼ・
repom 蝗ｺ譛峨・繧ゅ・・・test_redis_manager.py`縲～docker_manager/test_docker_manager_integration.py` 縺ｮ縺・■
`config` 縺ｨ邨仙粋縺励※縺・ｋ繧ゅ・縲～test_auto_import_models.py` 遲会ｼ峨・ repom 蛛ｴ縺ｫ谿九＠縲（mport 繝代せ縺縺・`basekit.X` 縺ｫ蛻・ｊ譖ｿ縺医ｋ縲・
### basekit 縺ｮ繝舌・繧ｸ繝ｧ繝ｳ pin 譖ｴ譁ｰ

[pyproject.toml:66-67](../../../pyproject.toml#L66-L67) 縺ｮ `[tool.uv.sources]` 縺ｧ basekit 繧・git 縺ｮ蝗ｺ螳・rev 謖・ｮ壹↓縺励※縺・ｋ・・
```toml
[tool.uv.sources]
basekit = { git = "https://github.com/jjjun/basekit.git", rev = "ca97f2dba52120fa28c543678830d69b9ee608d9" }
```

basekit 蛛ｴ縺ｧ譛ｬ莉ｶ縺ｮ螟画峩繧・push 縺励◆縺ゅ→縲∵眠縺励＞ rev 縺ｫ荳翫￡繧句ｿ・ｦ√′縺ゅｋ縲・
## 蠖ｱ髻ｿ遽・峇

### 蜑企勁
- `repom/_/discovery.py`
- `repom/_/docker_compose.py`
- `repom/_/docker_manager.py`
- 荳翫′遨ｺ縺ｫ縺ｪ繧後・ `repom/_/__init__.py` 縺翫ｈ縺ｳ `repom/_/` 繝・ぅ繝ｬ繧ｯ繝医Μ閾ｪ菴・
### 菫ｮ豁｣
- `repom/utility.py`
- `repom/postgres/manage.py` / `repom/redis/manage.py`
  ・・super().__init__(data_path=...)` 蜻ｼ縺ｳ蜃ｺ縺苓ｿｽ蜉・・- `repom/scripts/repom_info.py` / `db_backup.py` / `db_restore.py`
- 蜷・ｨｮ繝・せ繝茨ｼ井ｸ願ｿｰ・・- 繧ｬ繧､繝・3 譛ｬ・井ｸ願ｿｰ・・- `pyproject.toml` 縺ｮ basekit `rev` 譖ｴ譁ｰ
- `CLAUDE.md` 縺ｫ `repom/_/` 縺ｮ險倩ｿｰ縺後≠繧後・謨ｴ逅・ｼ・*迴ｾ譎らせ縺ｧ險倩ｿｰ縺ｪ縺励ｒ遒ｺ隱・*・・
### basekit 蛛ｴ霑ｽ蜉
- `src/basekit/discovery.py`
- `src/basekit/docker_compose.py`
- `src/basekit/docker_manager.py`
- 蜷・Δ繧ｸ繝･繝ｼ繝ｫ縺ｮ蜊倅ｽ薙ユ繧ｹ繝・- `src/basekit/__init__.py` 縺ｧ蜈ｬ髢・API 繧貞・繧ｨ繧ｯ繧ｹ繝昴・繝茨ｼ井ｻｻ諢上ょ茜逕ｨ蛛ｴ縺ｯ蝓ｺ譛ｬ `from basekit.X` 邨檎罰縺ｪ縺ｮ縺ｧ蠢・医〒縺ｯ縺ｪ縺・ｼ・- basekit 蛛ｴ繧ｬ繧､繝峨・霑ｽ蜉・井ｻｻ諢擾ｼ・
## 螳溯｣・ｨ育判

### Phase 1: basekit 蛛ｴ縺ｧ 3 繝｢繧ｸ繝･繝ｼ繝ｫ繧定ｿｽ蜉・亥渕逶､菴懊ｊ・・
1. `src/basekit/discovery.py` 繧・`repom/_/discovery.py` 縺九ｉ **縺昴・縺ｾ縺ｾ繧ｳ繝斐・** 縺ｧ菴懈・
2. `src/basekit/docker_compose.py` 繧貞酔讒倥↓ **縺昴・縺ｾ縺ｾ繧ｳ繝斐・** 縺ｧ菴懈・
3. `src/basekit/docker_manager.py` 繧・**蜀崎ｨｭ險・* 縺ｧ菴懈・
   - 繝｢繧ｸ繝･繝ｼ繝ｫ繝医ャ繝励・ `from repom.config import config` 繧貞炎髯､
   - `DockerManager.__init__(self, *, data_path)` 繧定ｿｽ蜉縺・`self._data_path` 繧剃ｿ晄戟
   - `get_compose_dir()` 繧・`self._data_path` 繝吶・繧ｹ縺ｫ菫ｮ豁｣
   - `get_generate_hint()` 繝｡繧ｽ繝・ラ繧貞・繧雁・縺・   - `validate_compose_file_exists()` 縺ｮ譌･譛ｬ隱樊枚險繧定恭隱槫喧
4. basekit `tests/unit_tests/` 縺ｫ 3 繝｢繧ｸ繝･繝ｼ繝ｫ縺ｶ繧薙・繝・せ繝医ｒ霑ｽ蜉
   - repom 蛛ｴ縺ｮ蟇ｾ蠢懊ユ繧ｹ繝医ｒ繧ｳ繝斐・縺励～from repom._.X` 竊・`from basekit.X` 縺ｫ螟画鋤
   - `DockerManager` 繝・せ繝医・ `config` 萓晏ｭ倡ｮ・園縺ｯ `data_path=tmp_path` 豕ｨ蜈･縺ｫ譖ｸ縺肴鋤縺・5. basekit 繝ｪ繝昴ず繝医Μ縺ｧ `uv run pytest` 邱代√さ繝溘ャ繝・& push縲∵眠縺励＞ `rev` 繧貞叙蠕・
### Phase 2: repom 蛛ｴ繧・basekit 縺ｫ蟾ｮ縺玲崛縺・
6. `pyproject.toml` 縺ｮ `[tool.uv.sources]` 縺ｧ basekit 繧呈眠 rev 縺ｫ譖ｴ譁ｰ
7. `uv lock` / `uv sync` 縺ｧ basekit 譖ｴ譁ｰ繧貞渚譏
8. 荳諡ｬ鄂ｮ謠・
   - `from repom._.discovery import ...` 竊・`from basekit.discovery import ...`
   - `from repom._.docker_compose import ...` 竊・`from basekit.docker_compose import ...`
   - `from repom._ import docker_manager as dm` 竊・`from basekit import docker_manager as dm`
   - patch 繧ｿ繝ｼ繧ｲ繝・ヨ `"repom._.docker_manager.XXX"` 竊・`"basekit.docker_manager.XXX"`
9. `PostgresManager` / `RedisManager` 縺ｮ `__init__` 縺ｫ
   `super().__init__(data_path=config.data_path)` 繧定ｿｽ蜉
10. `repom/_/discovery.py` / `repom/_/docker_compose.py` / `repom/_/docker_manager.py` 繧貞炎髯､
11. `repom/_/__init__.py` 縺ｮ荳ｭ霄ｫ繧堤｢ｺ隱阪・縺・∴縲∫ｩｺ縺ｾ縺溘・荳崎ｦ√↑繧牙炎髯､
12. `uv run pytest` 縺ｧ unit / behavior 蜿梧婿縺檎ｷ代〒縺ゅｋ縺薙→繧堤｢ｺ隱・
### Phase 3: 繝峨く繝･繝｡繝ｳ繝医・繧ｬ繧､繝画峩譁ｰ

13. `docs/guides/features/discovery_guide.md` / `docker_compose_guide.md` / `docker_manager_guide.md`
    縺ｮ import 萓九ｒ `basekit.X` 縺ｫ菫ｮ豁｣
14. 縲恵asekit 縺ｫ遘ｻ邂｡縺輔ｌ縺ｾ縺励◆縲肴葎繧貞・鬆ｭ縺ｫ霑ｽ險・15. basekit 繝ｪ繝昴ず繝医Μ縺ｫ繧ゅぎ繧､繝峨・邁｡譏鍋沿繧堤ｽｮ縺擾ｼ井ｻｻ諢擾ｼ・
### Phase 4: 螳御ｺ・・逅・
16. Issue 繧・`completed/066_move_shared_utilities_to_basekit.md` 縺ｫ遘ｻ蜍・17. `docs/issues/README.md` 繧呈峩譁ｰ
18. 繧ｳ繝溘ャ繝・ `docs(issue): Complete issue #066 - Move shared utilities to basekit`

## 繝・せ繝郁ｨ育判

- basekit 蛛ｴ
  - `uv run pytest` 縺ｧ discovery / docker_compose / docker_manager 縺ｮ繝ｦ繝九ャ繝医ユ繧ｹ繝亥・繝代せ
  - `DockerManager` 縺ｮ `data_path` 豕ｨ蜈･縺梧ｩ溯・縺励※縺・ｋ縺薙→繧・`tmp_path` 邨檎罰縺ｧ遒ｺ隱・- repom 蛛ｴ
  - `uv run pytest tests/unit_tests` 蜈ｨ繝代せ
  - `uv run pytest tests/behavior_tests` 蜈ｨ繝代せ
  - `uv run postgres_generate` / `uv run postgres_start` / `uv run redis_generate` 繧呈焔蜍輔〒螳溯｡後＠縲・    `data_path/postgres/` / `data_path/redis/` 驟堺ｸ九↓ compose 繝輔ぃ繧､繝ｫ縺檎函謌舌＆繧後√さ繝ｳ繝・リ縺瑚ｵｷ蜍輔☆繧九％縺ｨ繧堤｢ｺ隱・  - `uv run repom_info` 縺・PostgreSQL 謗･邯壽ュ蝣ｱ繧定｡ｨ遉ｺ縺ｧ縺阪ｋ縺薙→繧堤｢ｺ隱・
## 繝ｪ繧ｹ繧ｯ繝ｻ逡呎э轤ｹ

- **`pyproject.toml` 縺ｮ rev 譖ｴ譁ｰ繧ｿ繧､繝溘Φ繧ｰ**: basekit 蛛ｴ縺後・繝ｼ繧ｸ縺輔ｌ縺ｦ縺・↑縺・憾諷九〒 repom 蛛ｴ繧帝ｲ繧√ｋ縺ｨ
  uv 縺梧眠縺励＞繝｢繧ｸ繝･繝ｼ繝ｫ繧定ｧ｣豎ｺ縺ｧ縺阪↑縺・１hase 1 繧貞ｮ御ｺ・＠ basekit 縺ｫ commit/push 縺励※縺九ｉ Phase 2 縺ｫ蜈･繧九・- **`repom._` 縺ｮ patch 繧ｿ繝ｼ繧ｲ繝・ヨ譖ｸ縺肴鋤縺域ｼ上ｌ**: 繝・せ繝医・ `unittest.mock.patch` 譁・ｭ怜・縺ｯ
  grep 縺ｧ邯ｲ鄒・＠縺ｦ縺・ｋ縺後∫ｽｮ謠帶凾縺ｫ霑ｽ蜉繝輔ぃ繧､繝ｫ縺後↑縺・°譛邨ら｢ｺ隱阪☆繧九・- **fast-domain 縺ｪ縺ｩ螟夜Κ蛻ｩ逕ｨ閠・*: 迴ｾ迥ｶ `repom._.docker_manager` 繧堤峩謗･ import 縺励※縺・ｋ螟夜Κ繝励Ο繧ｸ繧ｧ繧ｯ繝医′
  縺ゅｌ縺ｰ螢翫ｌ繧具ｼ郁ｦ・grep・峨ゆｺ呈鋤諤ｧ繧定・・縺励↑縺・婿驥昴↑縺ｮ縺ｧ螢翫＠縺ｦ繧医＞縺後∝ｽｱ髻ｿ遽・峇縺ｯ蛻･騾泌・譛峨☆繧九・- **`get_compose_dir()` 縺ｮ data_path 隗｣豎ｺ**: basekit 蛛ｴ縺ｧ `data_path` 繧・None 縺ｮ縺ｾ縺ｾ貂｡縺輔ｌ縺溘こ繝ｼ繧ｹ縺ｮ
  謇ｱ縺・ｒ險ｭ險茨ｼ・ValueError` 繧呈兜縺偵ｋ縺九～Path.cwd() / "data"` 繧呈里螳壹↓縺吶ｋ縺具ｼ峨ｒ豎ｺ繧√ｋ縲・  repom 蛛ｴ縺九ｉ縺ｯ蟶ｸ縺ｫ `config.data_path` 繧呈ｸ｡縺吶・縺ｧ蝠城｡後・蜃ｺ縺ｪ縺・′縲｜asekit 蜊倅ｽ灘茜逕ｨ閠・髄縺代・
  繧ｬ繝ｼ繝我ｻ墓ｧ倥ｒ譁・嶌蛹悶☆繧九・
## 髢｢騾｣繝ｪ繧ｽ繝ｼ繧ｹ

- 譌｢蟄・repom 蛛ｴ繝輔ぃ繧､繝ｫ: [repom/_/discovery.py](../../../repom/_/discovery.py),
  [repom/_/docker_compose.py](../../../repom/_/docker_compose.py),
  [repom/_/docker_manager.py](../../../repom/_/docker_manager.py)
- basekit 繝ｪ繝昴ず繝医Μ: [C:/Users/jj/Desktop/workspace_main/projects/basekit](C:/Users/jj/Desktop/workspace_main/projects/basekit)
- 譌｢蟄倥ユ繧ｹ繝・ `tests/unit_tests/test_discovery_helpers.py`,
  `tests/unit_tests/test_docker_compose.py`, `tests/unit_tests/docker_manager/`
- 譌｢蟄倥ぎ繧､繝・ [docs/guides/features/discovery_guide.md](../../guides/features/discovery_guide.md),
  [docs/guides/features/docker_compose_guide.md](../../guides/features/docker_compose_guide.md),
  [docs/guides/features/docker_manager_guide.md](../../guides/features/docker_manager_guide.md)
- 髢｢騾｣螳御ｺ・issue:
  [completed/025_generic_package_discovery_infrastructure.md](../completed/025_generic_package_discovery_infrastructure.md),
  [completed/038_postgresql_container_customization.md](../completed/038_postgresql_container_customization.md),
  [completed/040_docker_management_base_infrastructure.md](../completed/040_docker_management_base_infrastructure.md),
  [completed/062_postgres_redis_compose_dir_unification.md](../completed/062_postgres_redis_compose_dir_unification.md)

