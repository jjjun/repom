# Issue #045: Docker Compose プロジェクト名を container_name ベースに簡素化

**ステータス**: ✅ 完了

**作成日**: 2026-02-24

**完了日**: 2026-02-24

**優先度**: 中

**関連Issue**: #043（ディレクトリ分離）、#044（project_name config 対応 → **本 Issue で廃止**）

---

## 問題の説明

### 現象

```bash
$ poetry run redis_start
✅ Generated: C:\...\data\repom\redis\docker-compose.generated.yml
   ...
🐳 Starting fast_domain_redis container...
Creating volume "fast_domain_fast_domain_redis_data" with default driver
WARNING: Found orphan containers (fast_domain_postgres, fast_domain_pgadmin) for this project. 
If you removed or renamed this service in your compose file, you can run this command with the --remove-orphans flag to clean it up.
Creating fast_domain_redis ... done
⏳ Waiting for service to be ready...
✅ fast_domain_redis is ready
```

### 根本原因

Issue #044 で `config.project_name` による `-p` オプションを実装したが、**Redis と PostgreSQL が同じプロジェクト名を使用している**ため、依然として orphan warning が発生する。

```bash
# 現在の動作
docker-compose -p fast_domain -f redis/docker-compose.generated.yml up -d
docker-compose -p fast_domain -f postgres/docker-compose.generated.yml up -d

# 両方とも project_name = "fast_domain" 
# → docker-compose は同じプロジェクトとみなす
# → Redis 起動時に postgres/pgadmin が orphan として検出される
```

### 影響

1. **警告表示**: ユーザーが不安になる
2. **Docker Desktop GUI での操作問題**: 停止操作がうまく動作しない場合がある
3. **ログ汚染**: 無駄な警告出力

### 期待する動作

- Redis: `docker-compose -p fast_domain_redis ...`
- PostgreSQL: `docker-compose -p fast_domain_postgres ...`
- 各サービスが独立したプロジェクトとして管理される
- orphan warning は表示されない
- Docker Desktop GUI で個別に管理可能

---

## 提案される解決策

### アプローチ: container_name をプロジェクト名として使用（project_name 廃止）

`config.project_name` を廃止し、既存の `get_container_name()` をプロジェクト名として使用する。

```python
# docker_manager.py（基底クラス）
class DockerManager(ABC):
    
    def get_project_name(self) -> str:
        """Docker Compose プロジェクト名を取得
        
        container_name をそのままプロジェクト名として使用。
        これにより各サービスが独立したプロジェクトになる。
        
        Returns:
            コンテナ名（例: "fast_domain_redis", "fast_domain_postgres"）
        """
        return self.get_container_name()
```

### 理由

1. **container_name は必ず設定する** - ユーザーは常にコンテナ名を指定する
2. **project_name は冗長** - `{project_name}_redis` も本質的にはハードコード
3. **シンプルさ** - 新しいプロパティやメソッドを追加する必要がない
4. **一貫性** - コンテナ名 = プロジェクト名で管理が簡単

### 結果

```bash
# Redis: container_name = "fast_domain_redis"
docker-compose -p fast_domain_redis -f redis/docker-compose.generated.yml up -d

# PostgreSQL: container_name = "fast_domain_postgres"
docker-compose -p fast_domain_postgres -f postgres/docker-compose.generated.yml up -d

# 完全に独立したプロジェクト → orphan warning なし ✅
```

---

## 影響範囲

### 変更対象ファイル

1. `repom/_/config_hook.py`
   - `_project_name` フィールド削除
   - `project_name` プロパティ削除

2. `repom/_/docker_manager.py`
   - `get_project_name()` を `get_container_name()` を返すように変更

3. `tests/unit_tests/test_config.py`
   - `project_name` 関連テスト削除

4. `tests/unit_tests/test_redis_manager.py`
   - `project_name` テストを `container_name` ベースに変更

5. `tests/unit_tests/test_postgres_manager.py`
   - 同上

6. `docs/guides/` のガイド
   - `project_name` 設定例を削除

### Docker Desktop GUI

- Redis: `fast_domain_redis` として表示
- PostgreSQL: `fast_domain_postgres` として表示
- 個別に start/stop/remove 可能

---

## 実装計画

### Phase 1: config_hook.py から project_name を削除
1. `_project_name` フィールド削除
2. `project_name` プロパティ（getter/setter）削除

### Phase 2: docker_manager.py の変更
3. `get_project_name()` を `return self.get_container_name()` に変更

### Phase 3: テスト更新
4. `test_config.py` の `project_name` テスト削除
5. `test_redis_manager.py` / `test_postgres_manager.py` のテスト修正

### Phase 4: ドキュメント更新
6. ガイドから `project_name` 設定例を削除

### Phase 5: 検証
7. 全テスト通過確認
8. 手動テスト: Redis と PostgreSQL の同時起動で orphan warning なし

---

## テスト計画

### 自動テスト

- [ ] `get_project_name()` が `get_container_name()` と同じ値を返すこと
- [ ] 既存の Docker 管理テストが通ること
- [ ] `config.project_name` が存在しないこと（AttributeError）

### 手動テスト

- [ ] Redis 起動後に PostgreSQL 起動で orphan warning が出ないこと
- [ ] PostgreSQL 起動後に Redis 起動で orphan warning が出ないこと
- [ ] Docker Desktop GUI で `fast_domain_redis` と `fast_domain_postgres` が別プロジェクトとして表示されること
- [ ] Docker Desktop GUI で個別に stop/remove できること

---

## 関連リソース

- [repom/_/docker_manager.py](../../../repom/_/docker_manager.py)
- [repom/_/config_hook.py](../../../repom/_/config_hook.py)
- [Issue #043: Docker Compose プロジェクト名の分離](../completed/043_docker_compose_project_separation.md)
- [Issue #044: Compose Project Name Config](../completed/044_compose_project_name_config.md)（本 Issue で廃止）
