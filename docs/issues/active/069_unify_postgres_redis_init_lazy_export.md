# Issue #69: `repom/redis/__init__.py` の遅延 import `__getattr__` を削除

**ステータス**: 🔴 未着手

**作成日**: 2026-05-19

**優先度**: 低

## 問題の説明

`repom/redis/__init__.py` と `repom/postgres/__init__.py` で公開 API の構造が非対称になっている。

- [repom/redis/__init__.py:6-19](../../../repom/redis/__init__.py#L6-L19) — `__getattr__` で `generate / start / stop / remove / get_compose_dir / get_init_dir / RedisManager` を `repom.redis.manage` から遅延 import
- [repom/postgres/__init__.py](../../../repom/postgres/__init__.py) — 同等の `__getattr__` 無し、Config 関連のみを公開

## 消費プロジェクト調査結果（2026-05-19）

`fast-domain` と `mine-py` の両方を grep で確認した結果、**`from repom.redis import generate|start|stop|remove|RedisManager` の使用は存在しない**:

- fast-domain: `from repom.redis.manage import ensure_running` / `from repom.redis.manage import generate` 等、いずれも submodule (`repom.redis.manage`) 経由で直接 import
- mine-py: `repom.redis` への import 自体が無い

→ `repom/redis/__init__.py` の `__getattr__` は完全に死んだ後方互換レイヤであることが確認できた。

## 提案される解決策（**A 案を採用**）

`repom/redis/__init__.py` から `__getattr__` を削除し、`__all__` を Config 公開のみに統一する（postgres 側と同じ形にする）:

```python
"""Redis Docker management and configuration module."""

from repom.redis.config import RedisConfig, RedisContainerConfig

__all__ = [
    "RedisConfig",
    "RedisContainerConfig",
]
```

外部利用者には `from repom.redis.manage import generate` 等の submodule 直接 import を案内する（既に両 consumer がその形式）。

## 影響範囲

- [repom/redis/__init__.py](../../../repom/redis/__init__.py)
- repom 内部テスト: `tests/unit_tests/test_redis_manage.py` は `from repom.redis.manage import ...` または `from repom.redis import manage` を使用しており影響なし

## 実装計画

1. `repom/redis/__init__.py` の `__getattr__` 関数と該当 `__all__` エントリを削除
2. `tests/unit_tests` を実行し回帰なきこと確認
3. `repom_info`、`redis_generate`、`postgres_generate` を実行し既存 CLI 経路を確認

## テスト計画

- 既存の `tests/unit_tests/test_redis_manage.py`、`test_postgres_manage.py` 全件パス
- `from repom.redis import generate` が `ImportError` を出すことを確認（追加テスト 1 件）
- `from repom.redis import RedisConfig` が引き続き動作することを確認

## 関連リソース

- [repom/redis/__init__.py](../../../repom/redis/__init__.py)
- [repom/postgres/__init__.py](../../../repom/postgres/__init__.py)
- 関連完了 Issue: #062（compose_dir/init_dir 共通化）
