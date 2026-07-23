# Package discovery の責務境界

汎用 package discovery の実装と API は `basekit.discovery` が正本です。
repom は仕様を複製せず、SQLAlchemy モデル読み込みのために利用しています。

repom 固有の入口は `repom.utility.load_models()` です。この関数は
`config.model_locations` を `basekit.discovery.import_from_packages()` に渡し、
全モデル import 後に SQLAlchemy の `configure_mappers()` を実行します。

```python
from repom.utility import load_models

load_models(context="alembic_migration")
```

利用側プロジェクトでは通常、`CONFIG_HOOK` で対象と許可 prefix を設定します。

```python
def hook_config(config):
    config.model_locations = ["myapp.models"]
    config.allowed_package_prefixes = {"myapp.", "repom."}
    config.model_excluded_dirs = {"base", "mixin", "__pycache__"}
    return config
```

汎用 discovery helper を直接利用する場合は `basekit.discovery` から import
してください。repom が後方互換用に再 export する helper は新規コードの正本では
ありません。

関連資料:

- [モデル自動 import ガイド](auto_import_models_guide.md)
- [`repom/utility.py`](../../../repom/utility.py)
- [CONFIG_HOOK ガイド](config_hook_guide.md)
