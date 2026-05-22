# Issue #073: postgres / pgadmin の env override helper を `repom/config_hooks/` に追加

**ステータス**: 🔴 未着手

**作成日**: 2026-05-22

**優先度**: 中

## 問題の説明

現状、`repom/config_hooks/redis.py` に `apply_redis_env_overrides()` が用意されており、利用側プロジェクトの `config_hook.py` から呼び出すだけで `REDIS_PORT` を環境変数で上書きできる仕組みになっている。

一方、PostgreSQL の接続情報 (`user` / `password` / `host` / `port`) と pgAdmin の認証情報 (`email` / `password`) は同等のヘルパが存在せず、利用側プロジェクトで上書きしたい場合は各自で `os.getenv()` を書くことになり、以下の問題がある:

- 環境変数名の規約が repom 側に存在せず、プロジェクト間でばらつく
- バリデーション（型・値域）が重複実装される
- CI / 本番で secrets を env 経由で注入する標準パターンが提示されていない

また付随する問題として:

- [repom/config.py:12](repom/config.py#L12) で `apply_redis_env_overrides` を import しているが、`config.py` 内では使用されていない（呼び出しは [repom/config_hook.py:52](repom/config_hook.py#L52) のみ）。死に import になっている。

## 提案される解決策

### 方針

`repom/config_hooks/` 配下を「環境変数からの上書き専用ヘルパー置き場」として明確化し、postgres / pgadmin 版を redis.py と同じ薄さで追加する。利用側プロジェクトは `config_hook.py` 内で必要なものだけ明示的に呼び出す。

### 環境変数の命名規約

PostgreSQL / pgAdmin の公式 Docker イメージが使う環境変数名にそのまま乗る。理由は (1) 利用者にとって直感的、(2) docker-compose 生成側と同じ env を共有でき、「env を変えれば両方変わる」状態を保てる。

| 設定 | 環境変数 |
|---|---|
| `config.postgres.user` | `POSTGRES_USER` |
| `config.postgres.password` | `POSTGRES_PASSWORD` |
| `config.postgres.host` | `POSTGRES_HOST` |
| `config.postgres.port` | `POSTGRES_PORT` |
| `config.pgadmin.email` | `PGADMIN_DEFAULT_EMAIL` |
| `config.pgadmin.password` | `PGADMIN_DEFAULT_PASSWORD` |

注: `POSTGRES_USER` / `POSTGRES_PASSWORD` は postgres Docker イメージがコンテナ初期化時のスーパーユーザー作成にも使う環境変数。本 Issue では「同じ値をクライアント接続情報にも使う」前提で公式名を共有する。

### API

`redis.py` と同じシグネチャ・粒度に揃える:

```python
# repom/config_hooks/postgres.py
def apply_postgres_env_overrides(config) -> None:
    """Apply PostgreSQL runtime overrides from environment variables.

    Reads: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
    """
    ...

# repom/config_hooks/pgadmin.py
def apply_pgadmin_env_overrides(config) -> None:
    """Apply pgAdmin runtime overrides from environment variables.

    Reads: PGADMIN_DEFAULT_EMAIL, PGADMIN_DEFAULT_PASSWORD
    """
    ...
```

バリデーション方針:
- `POSTGRES_PORT` は redis.py と同様に整数 + 1-65535 範囲チェック
- それ以外の文字列は空文字のみ拒否し、形式チェックはしない（接続失敗時のエラーに委ねる）
- redis.py の `getattr(config, "redis", None)` ガードは過剰なので、postgres/pgadmin 版では入れない（`RepomConfig` は必ず該当フィールドを持つ）

### 利用側からの呼び出し順

`config_hook.py` 内で「ハードコードしたデフォルト → env で上書き」の順を守る:

```python
# 利用側プロジェクト
config.postgres.user = 'mine_py'
config.postgres.password = 'dev_password'
config.pgadmin.email = 'admin@mine.local'

apply_postgres_env_overrides(config)
apply_pgadmin_env_overrides(config)
apply_redis_env_overrides(config)
```

## 影響範囲

### 新規作成
- `repom/config_hooks/postgres.py`
- `repom/config_hooks/pgadmin.py`
- `tests/unit_tests/config_hooks/test_postgres_env_overrides.py`
- `tests/unit_tests/config_hooks/test_pgadmin_env_overrides.py`

### 修正
- [repom/config.py:12](repom/config.py#L12) — 未使用 import (`apply_redis_env_overrides`) を削除
- [repom/config_hook.py](repom/config_hook.py) — repom 自身のフックに `apply_postgres_env_overrides` / `apply_pgadmin_env_overrides` の呼び出し例を追加
- [repom/config_hooks/redis.py](repom/config_hooks/redis.py) — docstring を「環境変数からの上書き専用ヘルパー置き場」と明記する形に揃える（コード変更なし）

### 利用側プロジェクトへの影響
- 既存の `config_hook.py` には強制的な影響なし（呼び出さなければ何も起こらない）
- 各プロジェクトの README / 移行ガイドで「env override を使いたい場合は `apply_xxx_env_overrides()` を呼ぶ」と案内する（→ proposal 化を検討）

## 実装計画

1. [repom/config.py:12](repom/config.py#L12) の未使用 import を削除
2. `repom/config_hooks/postgres.py` を新規作成
   - `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_PORT` を読み取る
   - port は int 変換 + 1-65535 範囲チェック
3. `repom/config_hooks/pgadmin.py` を新規作成
   - `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` を読み取る
4. `repom/config_hook.py` に呼び出し例を追加
5. unit tests を追加（環境変数あり / なし / 不正値の3パターン）
6. 各 helper の docstring に対応する環境変数名と用途を明記

## テスト計画

`tests/unit_tests/config_hooks/test_redis_env_overrides.py` 相当のテストを postgres / pgadmin について作成:

- **postgres**:
  - env が未設定の場合は config に変更なし
  - 各 env が単独で設定された場合に対応するフィールドが上書きされる
  - `POSTGRES_PORT` が非整数の場合 `ValueError`
  - `POSTGRES_PORT` が範囲外の場合 `ValueError`
- **pgadmin**:
  - env が未設定の場合は config に変更なし
  - 各 env が単独で設定された場合に対応するフィールドが上書きされる

`monkeypatch.setenv` / `monkeypatch.delenv` を使い、テスト間で env を汚染しない形にする。

## 関連リソース

- [repom/config_hooks/redis.py](repom/config_hooks/redis.py) — 参考実装
- [repom/postgres/config.py](repom/postgres/config.py) — `PostgresConfig` / `PgAdminConfig` 定義
- [repom/config.py](repom/config.py) — `RepomConfig`（修正対象）
- [repom/config_hook.py](repom/config_hook.py) — repom 自身のフック（修正対象）
- PostgreSQL Docker image: `POSTGRES_USER` / `POSTGRES_PASSWORD` 仕様（同名 env を共有する判断の根拠）
- pgAdmin Docker image: `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` 仕様
