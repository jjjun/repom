# Issue #72: `postgres/manage.py` / `redis/manage.py` のモジュール関数 `get_compose_dir` / `get_init_dir` を削除

**ステータス**: 🔴 未着手

**作成日**: 2026-05-19

**優先度**: 低

## 問題の説明

#062 で compose_dir / init_dir 解決ロジックを `DockerManager` に集約した際、後方互換のため `postgres/manage.py` と `redis/manage.py` にモジュールレベルの薄いラッパ関数を残した。

[repom/postgres/manage.py:18-24, 92-98](../../../repom/postgres/manage.py#L18-L24):

```python
def get_compose_dir():
    return PostgresManager().get_compose_dir()

def get_init_dir():
    return PostgresManager().get_init_dir()
```

[repom/redis/manage.py:18-24, 78-84](../../../repom/redis/manage.py#L18-L24) も同形。

## 消費プロジェクト調査結果（2026-05-19）

`fast-domain` と `mine-py` を grep で確認した結果、**外部 consumer は `get_compose_dir` / `get_init_dir` を一切呼び出していない**:

- fast-domain: `from repom.postgres.manage import ensure_running / generate / start / stop / remove` のみ
- mine-py: `repom.postgres` / `repom.redis` への import 自体が無い

repom 内部での利用箇所:
- [repom/postgres/manage.py:133, 172, 230, 236](../../../repom/postgres/manage.py#L133) — 同ファイル内の `generate_docker_compose()` / `generate()` から呼び出し
- [repom/redis/manage.py:125, 160, 166](../../../repom/redis/manage.py#L125) — 同ファイル内の `generate_docker_compose()` / `generate()` から呼び出し
- [tests/unit_tests/test_postgres_manage.py](../../../tests/unit_tests/test_postgres_manage.py): `from repom.postgres.manage import get_compose_dir` 等を 3 か所
- [tests/unit_tests/test_redis_manage.py](../../../tests/unit_tests/test_redis_manage.py): 同様

→ 互換ラッパとして残す根拠は失われている。

## 提案される解決策

1. モジュール関数 `get_compose_dir()` / `get_init_dir()` を **postgres/manage.py** / **redis/manage.py** から削除
2. 同ファイル内の呼び出し箇所を `Manager().get_compose_dir()` / `Manager().get_init_dir()` 直呼び、あるいは `generate()` 内で `manager` インスタンスを使い回す形に書き換え
3. repom 内部テストを Manager 経由のアクセスに更新

例:

```python
def generate():
    manager = PostgresManager()
    init_dir = manager.get_init_dir()
    ...
    compose_dir = manager.get_compose_dir()
    output_path = compose_dir / "docker-compose.generated.yml"
```

## 影響範囲

- [repom/postgres/manage.py](../../../repom/postgres/manage.py)
- [repom/redis/manage.py](../../../repom/redis/manage.py)
- [tests/unit_tests/test_postgres_manage.py](../../../tests/unit_tests/test_postgres_manage.py)
- [tests/unit_tests/test_redis_manage.py](../../../tests/unit_tests/test_redis_manage.py)
- 外部 consumer: 影響なし（grep 確認済み）

## 実装計画

1. postgres/redis 各々の `generate()` を `manager` インスタンス経由に書き換え
2. モジュール関数 `get_compose_dir()` / `get_init_dir()` を削除
3. 該当する単体テストの import を `from repom.postgres.manage import PostgresManager` 経由に更新
4. `uv run pytest tests/unit_tests` 全件パス
5. `repom_info`、`postgres_generate`、`redis_generate` で動作確認

## テスト計画

- 既存の test_postgres_manage / test_redis_manage 全件パス（更新後）
- `from repom.postgres.manage import get_compose_dir` が `ImportError` になることを確認

## 関連リソース

- 関連完了 Issue: #062（postgres/redis Manager の compose_dir/init_dir/compose_file_path 共通化）
- [repom/postgres/manage.py](../../../repom/postgres/manage.py)
- [repom/redis/manage.py](../../../repom/redis/manage.py)
