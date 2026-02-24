# Issue #046: volume_name のデフォルト値を container_name から自動生成

**ステータス**: ✅ 完了

**作成日**: 2026-02-24

**完了日**: 2026-02-24

**優先度**: 低

## 問題の説明

Docker コンテナ設定で `container_name` と `volume_name` を両方設定するのが冗長。

```python
# 現状: 両方設定が必要
config.postgres.container.container_name = "repom_postgres"
config.postgres.container.volume_name = "repom_postgres_data"  # 冗長
```

## 提案される解決策

`get_volume_name()` を変更し、`volume_name` が None の場合は `get_container_name() + "_data"` を返す。

```python
def get_volume_name(self) -> str:
    return self.volume_name or f"{self.get_container_name()}_data"
```

### 動作

| 設定 | get_volume_name() 結果 |
|------|------------------------|
| `volume_name = None` | `"{container_name}_data"` |
| `volume_name = "custom"` | `"custom"` （そのまま使用） |

### 使用例

```python
# container_name のみ設定
config.postgres.container.container_name = "repom_postgres"
# → get_volume_name() は "repom_postgres_data"

# volume_name を明示設定（そのまま使用）
config.redis.container.volume_name = "my_redis_vol"
# → get_volume_name() は "my_redis_vol"
```

## 影響範囲

- `repom/config.py` - 3 つの ContainerConfig クラス
- `repom/config_hook.py` - 冗長な `volume_name` 設定を削除

## 実装計画

1. `repom/config.py` の `get_volume_name()` を修正（3 箇所）
2. docstring 更新
3. `repom/config_hook.py` から `volume_name` 設定を削除
4. テスト実行

## 関連リソース

- Issue #038: PostgreSQL コンテナ設定のカスタマイズ対応
- Issue #042: Redis 設定管理と repom_info 統合
