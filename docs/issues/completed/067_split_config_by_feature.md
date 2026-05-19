**Status**: 完了
**作成日**: 2026-05-19
**優先度**: 中

# Issue #67: `repom/config.py` を機能別ファイルに分割し管理性を向上

## 問題の説明

[repom/config.py](../../../repom/config.py) は現在 **645 行** あり、以下の責務が単一ファイルに集約されている。

| dataclass | 行範囲 | 責務 |
|-----------|--------|------|
| `PostgresContainerConfig` | 13-39 | PostgreSQL Docker コンテナ |
| `PostgresConfig` | 42-61 | PostgreSQL 接続 + container 子設定 |
| `PgAdminContainerConfig` | 64-92 | pgAdmin Docker コンテナ |
| `PgAdminConfig` | 95-106 | pgAdmin 接続 + container 子設定 |
| `RedisContainerConfig` | 109-135 | Redis Docker コンテナ |
| `RedisConfig` | 138-155 | Redis 接続 + container 子設定 |
| `SqliteConfig` | 158-224 | SQLite ファイル/インメモリ設定 |
| `RepomConfig` | 227-634 | 上記を集約するトップレベル設定 |

`RepomConfig` 自体も `postgres_db` / `redis_port` / `db_url` / `engine_kwargs` などの計算プロパティ・docstring が肥大化しており、機能ごとの設定値とそれを束ねるコンポジション層が混在している。

### 参考: fast-domain の構成

[fast-domain の config.py](../../../../fast-domain/src/fast_domain/config.py) は同じ「機能毎に設定値を別ファイルにまとめる」パターンを採用しており、トップレベル `FastDomainConfig` は **248 行** に収まっている。

```python
# fast_domain/config.py の抜粋
from fast_domain.arq.config   import ArqConfig
from fast_domain.assets.config import AssetConfig
from fast_domain.auth.config  import AuthConfig
from fast_domain.db.config    import DatabaseConfig
from fast_domain.files.config import FileConfig
from fast_domain.info.config  import InfoConfig
from fast_domain.invoke.config import TaskConfig

@dataclass
class FastDomainConfig(Config):
    auth: AuthConfig   = field(default_factory=AuthConfig)
    arq:  ArqConfig    = field(default_factory=ArqConfig)
    db:   DatabaseConfig = field(default_factory=DatabaseConfig)
    ...
```

各機能ディレクトリの直下に `config.py` を置く方式で、機能と設定が同じ場所にまとまるため検索性・凝集性ともに高い。repom にも `repom/postgres/`, `repom/redis/` という機能ディレクトリが既に存在するので、同じパターンが自然に適用できる。

## 実現可能性

**結論: 可能**。技術的なブロッカーは無い。

- 各機能 dataclass は既に独立しており、`RepomConfig` 以外への循環依存はない。
- `SqliteConfig.bind(self)` は `RepomConfig` を後注入する設計のため、`SqliteConfig` を別ファイルへ移しても問題なく動作する（型ヒントは `from __future__ import annotations` または `TYPE_CHECKING` で前方参照可能）。
- 外部利用側は `from repom.config import RedisConfig, RedisContainerConfig, RepomConfig` のような import が既に存在する（例: [docs/guides/redis/redis_manager_guide.md:367](../../guides/redis/redis_manager_guide.md#L367)）。これらは `repom/config.py` から **再エクスポート** することで完全後方互換を維持できる。

## 提案される解決策

### 配置方針

機能ディレクトリ直下に `config.py` を置く（fast-domain と同じスタイル）。

```
repom/
├── config.py                # RepomConfig（集約 + 再エクスポート）
├── postgres/
│   ├── config.py            # NEW: PostgresConfig, PostgresContainerConfig,
│   │                        #      PgAdminConfig, PgAdminContainerConfig
│   └── manage.py
├── redis/
│   ├── config.py            # NEW: RedisConfig, RedisContainerConfig
│   └── manage.py
└── sqlite/                  # NEW: 新規モジュール
    ├── __init__.py
    └── config.py            # NEW: SqliteConfig
```

`repom/sqlite/` モジュールはまだ存在しないが、SQLite 関連のコードが将来増えた場合の置き場としても自然。最小では `__init__.py` と `config.py` のみで足りる。

> 代案: 「機能ディレクトリを増やしたくない」場合は `repom/sqlite/config.py` の代わりに `repom/config_sqlite.py` という同階層ファイルにする選択肢もある。実装フェーズで判断する。

### 後方互換の取り方

`repom/config.py` は引き続き再エクスポートを行い、既存の import パスを壊さない。

```python
# repom/config.py
from repom.postgres.config import (
    PostgresConfig,
    PostgresContainerConfig,
    PgAdminConfig,
    PgAdminContainerConfig,
)
from repom.redis.config import RedisConfig, RedisContainerConfig
from repom.sqlite.config import SqliteConfig

@dataclass
class RepomConfig(Config):
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    pgadmin:  PgAdminConfig  = field(default_factory=PgAdminConfig)
    redis:    RedisConfig    = field(default_factory=RedisConfig)
    sqlite:   SqliteConfig   = field(default_factory=SqliteConfig)
    ...
```

これにより以下の既存 import は全て無修正で動作する：

- `from repom.config import RepomConfig`
- `from repom.config import RedisConfig, RedisContainerConfig`
- `from repom.config import config`

### `RepomConfig` 側で残すもの

純粋に「集約・横断ロジック」だけを残す:

- `db_type` / `db_name` / `db_url` プロパティ（複数機能をまたぐ）
- `postgres_db` プロパティ（exec_env と db_name の組合せ）
- `engine_kwargs` プロパティ（db_type で分岐）
- `db_backup_path` / `master_data_path` プロパティ
- `enable_sqlalchemy_echo` / `sqlalchemy_echo_level` プロパティ
- モデル自動インポート設定（`model_locations` ほか）

機能固有の値（host/port/container 設定など）は各 `*/config.py` 側に移す。

### さらに踏み込んだ整理（オプション）

`redis_port` プロパティ ([config.py:370-384](../../../repom/config.py#L370-L384)) は `RedisConfig.port` と二重管理になっている。これは Issue 本筋とは別だが、分割作業中に統合・廃止可否を検討するとよい（環境変数 `REDIS_PORT` の上書き動作を残すかどうかが判断ポイント）。

## 影響範囲

### 移動するクラス（実装本体）

[repom/config.py](../../../repom/config.py) → 各 `*/config.py`

- `PostgresContainerConfig`, `PostgresConfig`, `PgAdminContainerConfig`, `PgAdminConfig`
- `RedisContainerConfig`, `RedisConfig`
- `SqliteConfig`

### 再エクスポートが必要なドキュメント・コード（無修正で動作させる対象）

- [docs/guides/redis/redis_manager_guide.md:367](../../guides/redis/redis_manager_guide.md#L367) — `from repom.config import RepomConfig, RedisConfig, RedisContainerConfig`
- [docs/guides/redis/redis_manager_guide.md](../../guides/redis/redis_manager_guide.md), [docs/guides/redis/README.md](../../guides/redis/README.md)
- [docs/guides/postgresql/postgresql_setup_guide.md](../../guides/postgresql/postgresql_setup_guide.md)
- [docs/guides/features/config_hook_guide.md](../../guides/features/config_hook_guide.md)

### テスト（参照のみ、import パスは互換維持で無修正でよい）

- [tests/unit_tests/test_postgres_container_config.py](../../../tests/unit_tests/test_postgres_container_config.py)
- [tests/unit_tests/test_config_redis.py](../../../tests/unit_tests/test_config_redis.py)
- [tests/unit_tests/test_sqlite_config_db_file_property.py](../../../tests/unit_tests/test_sqlite_config_db_file_property.py)

将来的にテスト側も `from repom.postgres.config import ...` のような直接 import に書き換えてもよいが、本 Issue では **互換性維持** に重点を置き必須としない。

### 外部プロジェクトへの影響

- fast-domain など外部利用側は `from repom.config import RepomConfig` 等のトップレベル import が中心であり、再エクスポートにより無影響。
- 影響を受ける可能性があるのは「`repom.config` モジュールに対する `mock.patch("repom.config.PostgresConfig")` のようなパッチ」を書いている場合だが、ワークスペース内では未検出。

## 実装計画

### Phase 1: PostgreSQL/pgAdmin 設定の分離

1. `repom/postgres/config.py` を新規作成し、`PostgresContainerConfig`/`PostgresConfig`/`PgAdminContainerConfig`/`PgAdminConfig` を移植。
2. `repom/config.py` から該当クラスを削除し、`from repom.postgres.config import ...` で再エクスポート。
3. `uv run pytest tests/unit_tests` で回帰確認。

### Phase 2: Redis 設定の分離

4. `repom/redis/config.py` を新規作成し、`RedisContainerConfig`/`RedisConfig` を移植。
5. `repom/config.py` から該当クラスを削除し再エクスポート。
6. `uv run pytest tests/unit_tests/test_config_redis.py tests/unit_tests/test_redis_manager.py` で回帰確認。

### Phase 3: SQLite 設定の分離

7. `repom/sqlite/__init__.py` と `repom/sqlite/config.py` を新規作成し、`SqliteConfig` を移植。
   - `bind()` の型注釈は `from __future__ import annotations` を入れて前方参照で `RepomConfig` を参照。
8. `repom/config.py` から `SqliteConfig` を削除し再エクスポート。
9. `uv run pytest tests/unit_tests/test_sqlite_config_db_file_property.py` で回帰確認。

### Phase 4: `RepomConfig` 周辺のクリーンアップ

10. `repom/config.py` 内に残った docstring・コメント・import を整理。
11. `redis_port` プロパティと `RedisConfig.port` の二重管理について整理方針を決定（本 Issue 内で完了させるか別 Issue にするかを判断）。
12. `uv run pytest`（unit + behavior）で全体回帰確認。
13. `uv run repom_info` / `uv run postgres_generate` / `uv run redis_generate` を手動実行し、CLI が正常動作することを確認。

### Phase 5: ドキュメント

14. [docs/guides/features/config_hook_guide.md](../../guides/features/config_hook_guide.md) に「機能別 config の場所」セクションを追記。
    - 既存サンプルの import パスは互換性のため `repom.config` 直接 import のまま残してよい。
    - 任意で `from repom.postgres.config import PostgresConfig` のような直接 import 例を併記。
15. 必要に応じて `CLAUDE.md` の `repom/` ディレクトリ構造説明を更新。

### Phase 6: 完了処理

16. Issue を `completed/067_split_config_by_feature.md` へ移動。
17. `docs/issues/README.md` を更新。
18. コミット: `refactor: split repom config into per-feature modules (#067)`

## テスト計画

- `tests/unit_tests` 全件パス（特に既存の `test_postgres_container_config.py` / `test_config_redis.py` / `test_sqlite_config_db_file_property.py`）。
- `tests/behavior_tests` 全件パス。
- 互換性テスト（追加または既存テスト内で確認）:
  - `from repom.config import RepomConfig, PostgresConfig, RedisConfig, SqliteConfig` がエラーなく動作する。
  - `RepomConfig().postgres` / `.redis` / `.sqlite` の型がそれぞれ移動先クラスの instance である。
- 手動確認:
  - `uv run repom_info`
  - `uv run postgres_generate` / `uv run redis_generate`
  - CONFIG_HOOK 経由のカスタマイズ（mine-py 等を想定）の代表ケース。

## リスク・留意点

- **循環 import**: `repom/postgres/config.py` 等で `RepomConfig` を型ヒントに使う場合は `from __future__ import annotations` + `TYPE_CHECKING` を併用する。`SqliteConfig.bind()` のみ該当する見込み。
- **再エクスポートの抜け**: 外部から import されるクラス・関数を網羅できているか、Phase ごとに `grep` で確認する。
- **fast-domain / mine-py 等の外部プロジェクト**: トップレベル `from repom.config import ...` のみを使っていれば無影響。`mock.patch("repom.config.XxxConfig")` を持っているプロジェクトがあれば事前周知。

## 関連リソース

- 対象ファイル: [repom/config.py](../../../repom/config.py)
- 参考実装: [fast-domain/src/fast_domain/config.py](../../../../fast-domain/src/fast_domain/config.py),
  [fast-domain/src/fast_domain/db/config.py](../../../../fast-domain/src/fast_domain/db/config.py)
- 関連ガイド:
  - [docs/guides/features/config_hook_guide.md](../../guides/features/config_hook_guide.md)
  - [docs/guides/redis/redis_manager_guide.md](../../guides/redis/redis_manager_guide.md)
  - [docs/guides/postgresql/postgresql_setup_guide.md](../../guides/postgresql/postgresql_setup_guide.md)
- 関連 issue:
  - [completed/042_redis_config_and_repom_info_integration.md](../completed/042_redis_config_and_repom_info_integration.md)
  - [completed/038_postgresql_container_customization.md](../completed/038_postgresql_container_customization.md)
  - [completed/047_db_name_prefix_customization.md](../completed/047_db_name_prefix_customization.md)
