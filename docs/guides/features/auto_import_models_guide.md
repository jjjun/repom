# SQLAlchemy モデル自動 import ガイド

repom は `repom.utility.load_models()` で利用側のモデル package を import し、
Alembic、DB script、test fixture から `Base.metadata` を参照できる状態にします。
汎用 discovery の API と実装は `basekit.discovery` が正本です。

## 設定

利用側プロジェクトの `CONFIG_HOOK` で次を設定します。

```python
def hook_config(config):
    config.model_locations = ["myapp.models"]
    config.allowed_package_prefixes = {"myapp.", "repom."}
    config.model_excluded_dirs = {
        "base",
        "mixin",
        "__pycache__",
    }
    config.model_import_strict = True
    return config
```

| 設定 | 役割 |
| --- | --- |
| `model_locations` | import する package 名の一覧 |
| `allowed_package_prefixes` | import を許可する package prefix |
| `model_excluded_dirs` | 再帰探索から除外する directory |
| `model_import_strict` | import failure を例外にするか |

`allowed_package_prefixes` は動的 import の境界です。利用側 package と、必要な場合だけ
`repom.` を明示してください。

## 実行

通常は console script と Alembic が自動的に `load_models()` を呼びます。診断時は
直接実行できます。

```python
from repom.utility import load_models

load_models(context="manual_check")
```

読み込み後の table は次のコマンドで確認できます。

```bash
uv run list_models
uv run repom_info
```

## 循環参照

`load_models()` は対象 package をすべて import した後に
`sqlalchemy.orm.configure_mappers()` を呼びます。文字列 relationship の参照先が
同じ `model_locations` 群から import できるように package を構成してください。

循環参照を避けるために個別 module の import 順へ依存するのではなく、モデル
package の `__init__.py` と `model_locations` を安定させます。

## テスト

`create_test_fixtures()` と `create_async_test_fixtures()` は、`model_loader` 未指定時に
`load_models()` を使います。テスト専用 loader が必要なら明示できます。

```python
from repom.testing import create_test_fixtures


def load_test_models():
    from tests.fixtures import models  # noqa: F401


db_engine, db_test = create_test_fixtures(
    db_url="sqlite:///:memory:",
    model_loader=load_test_models,
)
```

## エラーの確認

- `NoReferencedTableError`: 参照先モデルの package が `model_locations` に含まれるか確認。
- security error: 対象 package が `allowed_package_prefixes` に含まれるか確認。
- import failure が見えない: `model_import_strict=True` と詳細ログを有効にする。
- Alembic が table を検出しない: `alembic/env.py` が `load_models()` を呼んでいるか確認。

関連資料:

- [Discovery の責務境界](discovery_guide.md)
- [CONFIG_HOOK ガイド](config_hook_guide.md)
- [Testing Guide](../testing/testing_guide.md)
- [`repom/utility.py`](../../../repom/utility.py)
