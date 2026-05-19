# Issue #71: `repom/config.py` の後方互換 re-export を削除

**ステータス**: 🔴 未着手

**作成日**: 2026-05-19

**優先度**: 低

## 問題の説明

#067 で `RepomConfig` を機能別モジュールに分割した際、`repom/config.py` の `__all__` に PostgreSQL/pgAdmin/Redis/SQLite 関連 dataclass を後方互換のため再エクスポートとして残した。

[repom/config.py:441-451](../../../repom/config.py#L441-L451):

```python
__all__ = [
    "PgAdminConfig",
    "PgAdminContainerConfig",
    "PostgresConfig",
    "PostgresContainerConfig",
    "RedisConfig",
    "RedisContainerConfig",
    "RepomConfig",
    "SqliteConfig",
    "config",
]
```

## 消費プロジェクト調査結果（2026-05-19）

`fast-domain` と `mine-py` を grep で確認した結果、**外部 consumer は `from repom.config import` の Config 系クラスを一切使用していない**:

- 外部利用は `from repom.config import config as repom_config`（singleton）と `from repom.config import RepomConfig`（型ヒント / hook の親クラス）のみ
- Config クラス（PostgresConfig 等）は `config.postgres.container.container_name = ...` のように属性アクセスで使われており、クラス自体を import する必要は無い
- `RedisContainerConfig` / `PostgresContainerConfig` 等の検出は全て `submod/repom/tests/`（repom 自体のサブモジュールコピー）のみ

→ 再エクスポートは現時点で完全に死んだ後方互換レイヤ。

repom 内部テストの該当箇所:
- [tests/unit_tests/test_config_redis.py](../../../tests/unit_tests/test_config_redis.py): 8 か所が `from repom.config import RedisContainerConfig`
- [tests/unit_tests/test_postgres_container_config.py](../../../tests/unit_tests/test_postgres_container_config.py): `from repom.config import (...)` で複数クラスを import
- [tests/unit_tests/test_config_feature_modules.py](../../../tests/unit_tests/test_config_feature_modules.py): 機能別モジュールからの import との両方をテスト中

これらは feature module からの直接 import に置換可能。

## 提案される解決策

1. `repom/config.py` の `__all__` から以下を削除:
   - `PgAdminConfig`, `PgAdminContainerConfig`
   - `PostgresConfig`, `PostgresContainerConfig`
   - `RedisConfig`, `RedisContainerConfig`
   - `SqliteConfig`
2. 同ファイル上部の `from repom.{postgres,redis,sqlite}.config import ...` も基本的に不要だが、`RepomConfig` フィールド (`postgres: PostgresConfig = field(...)`) で必要なため、import 自体は残す。`__all__` から外すだけで OK
3. repom 内部テスト 3 ファイルの import を feature module 直接 import に変更
   - `from repom.config import RedisContainerConfig` → `from repom.redis.config import RedisContainerConfig`
   - 他も同様

CLAUDE.md / README にも「Config 系クラスは feature module から import する」旨を明記すれば、将来的に同様の互換 re-export が再発しない。

## 影響範囲

- [repom/config.py](../../../repom/config.py)
- [tests/unit_tests/test_config_redis.py](../../../tests/unit_tests/test_config_redis.py)
- [tests/unit_tests/test_postgres_container_config.py](../../../tests/unit_tests/test_postgres_container_config.py)
- [tests/unit_tests/test_config_feature_modules.py](../../../tests/unit_tests/test_config_feature_modules.py)
- 外部 consumer (`fast-domain` / `mine-py`): 影響なし（grep 確認済み）

## 実装計画

1. repom 内部テスト 3 ファイルの import を feature module へ変更
2. `tests/unit_tests` を実行し全件パス確認
3. `repom/config.py` の `__all__` から該当 6 エントリを削除
4. `repom_info` を実行し起動確認
5. fast-domain / mine-py の test を念のため実行（影響なしの再確認）

## テスト計画

- `uv run pytest tests/unit_tests` 全件パス
- 削除後、`from repom.config import RedisContainerConfig` が `ImportError` になることを確認
- fast-domain (`uv run pytest`) / mine-py 側もパス

## 関連リソース

- 関連完了 Issue: #067（`repom/config.py` を機能別ファイルに分割）
- [repom/postgres/config.py](../../../repom/postgres/config.py)
- [repom/redis/config.py](../../../repom/redis/config.py)
- [repom/sqlite/config.py](../../../repom/sqlite/config.py)
