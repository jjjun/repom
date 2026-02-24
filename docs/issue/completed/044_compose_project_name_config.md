# Issue #044: Compose Project Name Config

**ステータス**: ✅ 完了

**作成日**: 2026-02-24

**完了日**: 2026-02-24

**優先度**: 中

## 問題の説明

複数プロジェクト（repom / fast-domain）で Docker Compose を使うと、
compose のプロジェクト名がディレクトリ名由来で衝突する可能性がある。
現在は `COMPOSE_PROJECT_NAME` の環境変数で回避できるが、
config 経由で一元的に指定できない。

## 提案される解決策

ベース `Config` に `project_name` プロパティを追加し、`hook_config` で任意の名称を設定できるようにする。
Docker Compose 実行時に `-p <project_name>` を渡し、プロジェクト名衝突を防止する。

### 設計方針（確定）

1. **環境変数 `COMPOSE_PROJECT_NAME` は廃止**
   - config による一元管理に統一

2. **`project_name` のデフォルト値**
   - `config.package_name` を使用
   - `package_name` が `None` の場合は `"default"` にフォールバック

3. **実装パターン**
   ```python
   # repom/_/config_hook.py
   @dataclass
   class Config:
       _project_name: Optional[str] = field(default=None, init=False, repr=False)
       
       @property
       def project_name(self) -> str:
           """Docker Compose プロジェクト名（デフォルト: package_name）"""
           if self._project_name is not None:
               return self._project_name
           return self.package_name or "default"
       
       @project_name.setter
       def project_name(self, value: Optional[str]):
           self._project_name = value
   ```

4. **使用例**
   ```python
   # repom/config_hook.py
   def hook_config(config):
       config.project_name = "repom"  # 明示的に指定（省略可）
       return config
   
   # fast-domain/config_hook.py
   def hook_config(config):
       config.project_name = "fast_domain"
       return config
   ```

## 影響範囲

- `repom/_/config_hook.py` の `Config` クラス（`project_name` プロパティ追加）
- `repom/_/docker_manager.py` の `run_docker_compose()`（`-p` オプション追加）
- PostgreSQL / Redis / pgAdmin の compose 実行経路（`project_name` 引数追加）
- `docs/guides/` の運用ガイド（`project_name` 設定方法を追記）
- 既存テスト（Docker 管理テストの更新）

## 実装計画

### Phase 1: Config 基盤整備
1. `Config` クラスに `project_name` プロパティを追加
   - デフォルト: `self.package_name or "default"`
   - Setter/Getter 実装

### Phase 2: Docker Manager 統合
2. `run_docker_compose()` に `project_name` パラメータを追加
   - `-p <project_name>` オプションを渡す
   - `None` の場合は従来挙動（`-p` なし）

3. `DockerManager` 基底クラスに `get_project_name()` を追加
   - デフォルト実装: `return self.config.project_name`

### Phase 3: サービス別実装
4. PostgresManager / RedisManager で `get_project_name()` を使用
   - `start()` / `stop()` / `remove()` で `-p` を渡す

### Phase 4: テストとドキュメント
5. 単体テスト追加
   - `project_name` 未指定時のデフォルト挙動
   - `project_name` 指定時の `-p` 使用確認
   - 既存テストの互換性確認

6. ドキュメント更新
   - `config_hook_guide.md` に `project_name` 設定例を追加
   - PostgreSQL / Redis ガイドに複数プロジェクト運用例を追加

## テスト計画

- ✅ `project_name` 未指定時に `package_name` が使われること
- ✅ `package_name` も未指定時に `"default"` が使われること
- ✅ `project_name` 指定時に `docker-compose -p` が使用されること
- ✅ 既存の Docker 管理テストへの影響を確認
- ✅ repom / fast-domain の同時起動テスト（手動）

## 関連リソース

- [repom/_/docker_manager.py](../../repom/_/docker_manager.py)
- [repom/_/config_hook.py](../../repom/_/config_hook.py)
- [docs/guides/features/config_hook_guide.md](../guides/features/config_hook_guide.md)

---

## 実装結果（2026-02-24）

### 完了した作業

✅ **Phase 1: Config 基盤整備**
- `Config` クラスに `_project_name` フィールドと `project_name` プロパティ（getter/setter）を追加
- デフォルト値: `self.package_name or "default"`

✅ **Phase 2: Docker Manager 統合**
- `run_docker_compose()` に `project_name: Optional[str]` パラメータを追加
- `-p <project_name>` オプションを compose コマンドに渡す実装
- `DockerManager.get_project_name()` メソッドを追加（`self.config.project_name` を返す）

✅ **Phase 3: サービス別実装**
- PostgresManager / RedisManager は継承により自動対応
- `start()` / `stop()` / `remove()` で `project_name` が自動使用される

✅ **Phase 4: テストとドキュメント**
- `test_config.py` に 4 つの `project_name` プロパティテストを追加
- `test_redis_manager.py` に 3 つの `get_project_name()` テストを追加
- `test_postgres_manager.py` に 3 つの `get_project_name()` テストを追加
- 全単体テスト通過確認（608 tests passed）
- `config_hook_guide.md` に複数プロジェクト設定例を追加
- `postgresql_setup_guide.md` に `project_name` 設定例を追加
- `redis_manager_guide.md` に複数プロジェクト運用セクションを追加

### 実装の詳細

#### 1. Config クラス拡張（repom/_/config_hook.py）

```python
@property
def project_name(self) -> str:
    """Docker Compose プロジェクト名（デフォルト: package_name）"""
    if self._project_name is not None:
        return self._project_name
    return self.package_name or "default"

@project_name.setter
def project_name(self, value: Optional[str]):
    self._project_name = value
```

#### 2. Docker Compose 実行の変更（repom/_/docker_manager.py）

```python
def run_docker_compose(self, args: List[str], project_name: Optional[str] = None) -> subprocess.CompletedProcess:
    cmd = ["docker-compose"]
    if project_name is not None:
        cmd.extend(["-p", project_name])
    cmd.extend(["-f", str(compose_file)] + args)
    ...
```

#### 3. DockerManager 基底クラス拡張

```python
def get_project_name(self) -> str:
    """Docker Compose プロジェクト名を取得"""
    return self.config.project_name if hasattr(self.config, 'project_name') else "default"
```

### テスト結果

全単体テスト通過: **608 tests passed**
- Config プロパティテスト: 4 tests
- RedisManager project_name テスト: 3 tests
- PostgresManager project_name テスト: 3 tests

### ドキュメント更新

1. **config_hook_guide.md**
   - 複数プロジェクトでの Docker コンテナ分離セクション追加
   - project_name 設定例とその効果を説明

2. **postgresql_setup_guide.md**
   - 「複数プロジェクトでの並行開発」セクションを更新
   - project_name 設定の重要性を明記

3. **redis_manager_guide.md**
   - 「複数プロジェクトでの並行開発」セクションを新規追加
   - fast-domain プロジェクトの設定例を追加

### 効果

- ✅ Docker Compose プロジェクト名の衝突を回避
- ✅ 複数プロジェクト（repom / fast-domain / mine-py）の同時起動が可能
- ✅ 環境変数 `COMPOSE_PROJECT_NAME` に依存しない config ベースの管理
- ✅ コンテナ名の命名規則が統一（`<project_name>-<service>-1`）

### 今後の課題

すべて完了。追加作業なし。
