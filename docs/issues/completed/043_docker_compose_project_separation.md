# Issue #043: Docker Compose プロジェクト名の分離

**ステータス**: 🔴 未着手

**作成日**: 2026-02-23

**優先度**: 中

**関連Issue**: #040（Docker 管理基盤）、#041（Redis Docker 統合）、#042（Redis 設定統合）

---

## 問題の説明

### 現象

```bash
$ poetry run redis_start
✅ Generated: C:\...\docker-compose.generated.yml
   ...
🐳 Starting repom_redis container...
Creating volume "repom_repom_redis_data" with default driver
WARNING: Found orphan containers (repom_pgadmin, repom_postgres) for this project. 
If you removed or renamed this service in your compose file, you can run this...
📦 Redis Connection:
  ...
```

### 根本原因

Redis と PostgreSQL が以下の理由で同じプロジェクト名として認識されている：

1. **同じディレクトリに保存**: `data/repom/` に両方の `docker-compose.generated.yml` が保存される
2. **同じプロジェクト名**: デフォルトプロジェクト名 = `docker-compose.yml` があるディレクトリ名

```bash
# 現在の問題
docker-compose -f data/repom/docker-compose.generated.yml up -d
  ↓ デフォルトプロジェクト名 = "repom"
  ↓ Redis ファイルに postgres/pgadmin 定義がない → orphan と判定

# 解決策
docker-compose -f data/repom/redis/docker-compose.generated.yml up -d
  ↓ プロジェクト名 = "repom_redis"（ディレクトリ名から派生）
  ↓ orphan 検出なし ✅
```

### 影響

- Redis 起動時に PostgreSQL/pgAdmin が orphan として警告表示
- ユーザーが不安になる
- 無駄な警告出力でログが汚染される

### 期待する動作

- `redis_generate` → `data/repom/redis/` に Redis のみの docker-compose.yml を生成
- `postgres_generate` → `data/repom/postgres/` に PostgreSQL + pgAdmin の docker-compose.yml を生成
- 各サービスが独立したプロジェクトで管理される
- orphan warning は表示されない

---

## 解決策

### アプローチ：分離プロジェクト構造

ファイル構造を以下のように分離：

```
data/repom/
├── redis/
│   ├── docker-compose.generated.yml  ← Redis のみ
│   ├── redis_init/
│   │   └── redis.conf
│   └── ...
├── postgres/
│   ├── docker-compose.generated.yml  ← PostgreSQL + pgAdmin
│   ├── postgresql_init/
│   │   └── 01_init_databases.sql
│   ├── servers.json
│   └── ...
```

### Docker Compose プロジェクト名

```yaml
# data/repom/redis/docker-compose.generated.yml
# プロジェクト名は自動で "redis" に（ディレクトリ名から派生）
services:
  redis:
    image: redis:7-alpine
    container_name: repom_redis
    ...

# data/repom/postgres/docker-compose.generated.yml
# プロジェクト名は自動で "postgres" に（ディレクトリ名から派生）
services:
  postgres:
    image: postgres:16-alpine
    container_name: repom_postgres
    ...
  pgadmin:
    image: dpage/pgadmin:latest
    container_name: repom_pgadmin
    ...
```

### メリット

| 項目 | 現在 | 修正後 |
|-----|------|--------|
| **ファイル管理** | 1 ファイル（競合リスク） | 2 ファイル（独立） |
| **orphan warning** | ❌ 表示される | ✅ 消える |
| **実装複雑性** | 中程度 | 🟢 低い |
| **段階的有効化** | ⚠️ 難しい | 🟢 簡単 |
| **保守性** | 🟡 中程度 | 🟢 高い |
| **ファイル上書き競合** | ⚠️ あり（マージ必要） | ✅ なし |

---

## 実装計画

### Phase 1: `redis/manage.py` 修正
- [ ] `get_compose_dir()` を修正: `data/repom/redis/` に変更
- [ ] 既存の Redis 設定ファイルもこのディレクトリに生成
- [ ] `RedisManager.get_compose_file_path()` が新パスを参照することを確認

### Phase 2: `postgres/manage.py` 修正
- [ ] `get_compose_dir()` を修正: `data/repom/postgres/` に変更
- [ ] 既存の PostgreSQL 初期化ファイル、servers.json もこのディレクトリに生成
- [ ] `PostgresManager.get_compose_file_path()` が新パスを参照することを確認

### Phase 3: テスト
- [ ] `test_redis_manage.py` で `redis_generate` の新パスを検証
- [ ] `test_postgres_manage.py` で `postgres_generate` の新パスを検証
- [ ] `redis_generate` と `postgres_generate` の両方実行時に競合しないことを確認

### Phase 4: 動作確認
- [ ] `redis_generate` → `redis_start` で orphan warning が出ないか確認
- [ ] `postgres_generate` → `postgres_start` で orphan warning が出ないか確認
- [ ] Docker Desktop でプロジェクトが `redis` と `postgres` に分かれていることを確認

### Phase 5: ドキュメント更新
- [ ] README.md でディレクトリ構造を記載
- [ ] redis_manager_guide.md を作成（Redis Docker 管理の説明）
- [ ] postgres_manager_guide.md を作成（PostgreSQL Docker 管理の説明）

### Phase 6: マイグレーション処理
- [ ] 既存の `data/repom/docker-compose.generated.yml` を削除指示またはスクリプト化
- [ ] 既存ファイル中では古いファイルをバックアップするメッセージを表示

---

## 実装コード例

### `redis/manage.py` 修正

```python
def get_compose_dir() -> Path:
    """docker-compose.yml の保存先ディレクトリを取得
    
    Returns:
        config.data_path/redis/ ディレクトリ（変更点）
    """
    compose_dir = Path(config.data_path) / "redis"  # ← "/redis" を追加
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir


def get_init_dir() -> Path:
    """Redis 初期化ファイルのディレクトリを取得
    
    Returns:
        redis ディレクトリ直下の redis_init/
    """
    compose_dir = get_compose_dir()
    init_dir = compose_dir / "redis_init"
    init_dir.mkdir(parents=True, exist_ok=True)
    return init_dir
```

### `postgres/manage.py` 修正

```python
def get_compose_dir() -> Path:
    """docker-compose.yml の保存先ディレクトリを取得
    
    Returns:
        config.data_path/postgres/ ディレクトリ（変更点）
    """
    compose_dir = Path(config.data_path) / "postgres"  # ← "/postgres" を追加
    compose_dir.mkdir(parents=True, exist_ok=True)
    return compose_dir


def get_init_dir() -> Path:
    """PostgreSQL 初期化スクリプトのディレクトリを取得
    
    Returns:
        postgres ディレクトリ直下の postgresql_init/
    """
    compose_dir = get_compose_dir()
    init_dir = compose_dir / "postgresql_init"
    init_dir.mkdir(parents=True, exist_ok=True)
    return init_dir
```

---

## 影響範囲

### 修正ファイル

1. **repom/redis/manage.py** (~3行修正)
   - `get_compose_dir()` 関数を修正
   - `get_init_dir()` 関数を修正（参照を更新）

2. **repom/postgres/manage.py** (~3行修正)
   - `get_compose_dir()` 関数を修正
   - `get_init_dir()` 関数を修正（参照を更新）

3. **tests/unit_tests/test_redis_manage.py** (~5行追加)
   - 新しいディレクトリパスでの `redis_generate` テスト

4. **tests/unit_tests/test_postgres_manage.py** (~5行追加)
   - 新しいディレクトリパスでの `postgres_generate` テスト

5. **docs/README.md またはガイド** (新規・更新)
   - ディレクトリ構造の説明を追加

### 互換性への影響

✅ **破壊的変更なし**：
- Public API（コマンド）は変わらない
- ユーザーコマンド（`redis_generate`, `redis_start`, etc.）は同じ
- 外部プロジェクトの影響なし
- 既存ファイルは手動削除か、スクリプトでマイグレーション

---

## テスト計画

### Unit Tests

1. **redis_generate が `data/repom/redis/` に docker-compose.yml を生成**
   ```python
   def test_redis_generate_creates_in_redis_subdir():
       """redis_generate が redis サブディレクトリに生成"""
       redis_generate()
       
       compose_file = Path(config.data_path) / "redis" / "docker-compose.generated.yml"
       assert compose_file.exists()
   ```

2. **postgres_generate が `data/repom/postgres/` に docker-compose.yml を生成**
   ```python
   def test_postgres_generate_creates_in_postgres_subdir():
       """postgres_generate が postgres サブディレクトリに生成"""
       postgres_generate()
       
       compose_file = Path(config.data_path) / "postgres" / "docker-compose.generated.yml"
       assert compose_file.exists()
   ```

3. **redis_generate と postgres_generate の両方実行時に競合しない**
   ```python
   def test_no_conflict_between_services():
       """両サービス生成時に互いに影響しない"""
       redis_generate()
       postgres_generate()
       
       redis_compose = Path(config.data_path) / "redis" / "docker-compose.generated.yml"
       postgres_compose = Path(config.data_path) / "postgres" / "docker-compose.generated.yml"
       
       assert redis_compose.exists()
       assert postgres_compose.exists()
       
       # Redis ファイルに postgres が含まれていないことを確認
       redis_content = redis_compose.read_text()
       assert "postgres" not in redis_content
       assert "pgadmin" not in redis_content
   ```

### Integration Tests

1. **redis_start 実行時に orphan warning が出ないこと**
   - 前提: `redis_generate` で Redis docker-compose.yml を生成
   - `redis_start` 実行
   - stdout/stderr に "orphan containers" が含まれないことを確認

2. **postgres_start 実行時に orphan warning が出ないこと**
   - 前提: `postgres_generate` で PostgreSQL docker-compose.yml を生成
   - `postgres_start` 実行（redis が実行中でも）
   - stdout/stderr に "orphan containers" が含まれないことを確認

3. **Docker Desktop で独立したプロジェクトが表示される**
   - `redis_generate` → `redis_start` 実行
   - `postgres_generate` → `postgres_start` 実行
   - Docker Desktop で `redis` と `postgres` という 2 つの独立したプロジェクトが表示されることを確認
   - `repom_redis` は `redis` プロジェクト下に表示
   - `repom_postgres` と `repom_pgadmin` は `postgres` プロジェクト下に表示

---

## 関連リソース

- [Docker Compose プロジェクト名](https://docs.docker.com/compose/reference/compose_ps/)
- Issue #040: Docker 管理基盤実装
- Issue #041: Redis Docker 統合
- Issue #042: Redis 設定統合

---

## 備考

### なぜ分離プロジェクト構造か？

**メリット**:
1. **実装がシンプル**: 既存コードの `get_compose_dir()` 関数のパスを変更するだけ
2. **ファイル管理が容易**: 各サービスが独立したディレクトリ・ファイルを持つ
3. **段階的な有効化が簡単**: 後から Redis を追加する場合、PostgreSQL ファイルを変更しない
4. **保守性が高い**: サービスごとのコード変更が明確に分離
5. **テストが簡単**: 各サービスのテストが独立している

**トレードオフ**:
- Docker Desktop UI が分散表示される（`redis` と `postgres` の 2 プロジェクト）
  → ユーザーからの要望で許容範囲であることを確認済み

### Docker Compose プロジェクト名の決定方法

```bash
# プロジェクト名は以下の優先順位で決定される
1. -p オプション: docker-compose -p my_project ...
2. COMPOSE_PROJECT_NAME 環境変数
3. docker-compose.yml があるディレクトリ名

# 我々の場合
data/repom/redis/docker-compose.generated.yml
  → ディレクトリ名が "redis" → プロジェクト名 = "redis"

data/repom/postgres/docker-compose.generated.yml
  → ディレクトリ名が "postgres" → プロジェクト名 = "postgres"
```

---

**作成者**: GitHub Copilot  
**最終更新**: 2026-02-23
