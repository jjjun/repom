# Issue #62: postgres/redis Manager の compose_dir/init_dir/compose_file_path 共通化

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 低

## 問題の説明

`repom/postgres/manage.py` と `repom/redis/manage.py` で、サブディレクトリ名以外ほぼ同一のコードが重複している。

### `get_compose_dir()`

[repom/postgres/manage.py:19-27](../../../repom/postgres/manage.py#L19-L27)
```python
def get_compose_dir() -> Path:
    compose_dir = Path(config.data_path) / "postgres"
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir
```

[repom/redis/manage.py:19-27](../../../repom/redis/manage.py#L19-L27)
```python
def get_compose_dir() -> Path:
    compose_dir = Path(config.data_path) / "redis"
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir
```

### `get_init_dir()` も同様の構造
- postgres → `postgresql_init/`
- redis → `redis_init/`

### `get_compose_file_path()`
`PostgresManager.get_compose_file_path()` と `RedisManager.get_compose_file_path()` は compose_dir 取得関数が違うだけで、`docker-compose.generated.yml` の存在チェックとエラーメッセージのテンプレート（"Hint: Run '... _generate' first"）が完全に同形。

将来 MongoDB / Elasticsearch 等を追加する際にもさらに重複が増える構造。

## 提案される解決策

`repom/_/docker_manager.py` の `DockerManager` 基底クラスへ集約する。

```python
class DockerManager(ABC):
    SERVICE_NAME: ClassVar[str]   # サブクラスで指定（"postgres", "redis"）
    INIT_SUBDIR: ClassVar[str]    # サブクラスで指定（"postgresql_init", "redis_init"）
    GENERATE_COMMAND: ClassVar[str]  # ヒント表示用（"postgres_generate" 等）

    def get_compose_dir(self) -> Path:
        d = Path(config.data_path) / self.SERVICE_NAME
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_init_dir(self) -> Path:
        d = self.get_compose_dir() / self.INIT_SUBDIR
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_compose_file_path(self) -> Path:
        f = self.get_compose_dir() / "docker-compose.generated.yml"
        if not f.exists():
            raise FileNotFoundError(
                f"Compose file not found: {f}\n"
                f"Hint: Run 'uv run {self.GENERATE_COMMAND}' first"
            )
        return f
```

ただしモジュールレベル関数（`get_compose_dir()` / `get_init_dir()`）は他から import されている可能性があるため、後方互換のための薄いラッパを残すか、影響範囲を grep してから移行を判断する。

## 影響範囲

- `repom/_/docker_manager.py`（基底クラス拡張）
- `repom/postgres/manage.py`（重複削除）
- `repom/redis/manage.py`（重複削除）
- `repom/scripts/postgres_*.py` / `redis_*.py`（モジュール関数を呼んでいる場合は call site 修正）
- `repom/examples/` のサンプル

## 実装計画

1. `get_compose_dir` / `get_init_dir` / `get_compose_file_path` の呼び出し元を grep で洗い出し
2. `DockerManager` 基底クラスに 3 メソッドを実装
3. `PostgresManager` / `RedisManager` から重複実装を削除
4. モジュール関数は call site を Manager 経由に置き換えるか、deprecation を付けて残す
5. テスト

## テスト計画

- 既存の docker_manager / postgres_manager / redis_manager テスト全件パス
- `uv run postgres_generate` / `uv run redis_generate` の手動動作確認

## 関連リソース

- [repom/_/docker_manager.py](../../../repom/_/docker_manager.py)
- 関連完了 Issue: #040, #041, #042, #043, #045
