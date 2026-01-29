# Issue #023: Test Independence and Isolation Improvements

**ステータス**: 🟡 調査・設計段階

**作成日**: 2026-01-29

**優先度**: 中

**複雑度**: 高

---

## 問題の説明

現在のテストスイートには**テストの独立性（Test Isolation）**に関する複数の問題があり、一部のテストが実行順序に依存しています。これはテストの信頼性を低下させ、並列実行やランダム順序実行を妨げる要因となっています。

### 現状の問題点

#### 1. **グローバルステート（Base.metadata）への依存**

**問題**: SQLAlchemy の `Base.metadata` はすべてのテストで共有されるグローバルステート
- どのテストでも `Base.metadata` に直接アクセス可能
- 一度登録されたテーブルは削除されない（通常）
- 複数のテストが同じメタデータを汚染する可能性

**影響**:
```python
# test_A.py
class ModelA(BaseModel):
    __tablename__ = 'model_a'
    # → Base.metadata に 'model_a' が登録される

# test_B.py  
class ModelA(BaseModel):  # 同名クラス
    __tablename__ = 'model_a'  # 同名テーブル
    # → "Table 'model_a' is already defined" エラー
```

**現在の対処**:
- `extend_existing=True` を使用（回避策）
- テスト関数内でローカル定義（部分的）

#### 2. **isolated_mapper_registry の副作用**

**問題**: `isolated_mapper_registry` フィクスチャが `clear_mappers()` を呼び出し、**全テストに影響を与える**

**実装**:
```python
@pytest.fixture
def isolated_mapper_registry():
    """マッパーレジストリをクリアして隔離された環境を提供"""
    clear_mappers()  # ← すべてのマッパーをクリア
    Base.metadata.clear()  # ← すべてのテーブル定義を削除
    
    yield
    
    # テスト後の復元処理なし！
```

**影響**:
- このフィクスチャを使用したテストの**後**に実行されるテストが影響を受ける
- `Base.metadata` が空になり、期待するテーブルが存在しない
- 実行順序によってテストが成功/失敗する

**実例（Issue #021）**:
```
# 実行順序: test_alembic_env_loads_models.py → test_migration_no_id.py
test_alembic_env_loads_models.py (isolated_mapper_registry 使用)
    ↓ clear_mappers() でメタデータをクリア
test_migration_no_id.py
    ↓ Base.metadata が空で期待するモデルがない
    ↓ FAILURE: "Could not find test_migration_no_id table"
```

**現在の対処**:
- `test_00_migration_no_id.py` にリネーム（実行順序を制御）
- 根本的な解決ではない

#### 3. **テスト実行順序への依存**

**問題**: `test_00_migration_no_id.py` は**最初に実行される**ことが前提

**理由**:
- Alembic マイグレーションテストは `Base.metadata` が正しい状態を必要とする
- 他のテストが `isolated_mapper_registry` でメタデータをクリアする前に実行する必要

**問題点**:
- ❌ pytest の `-k` オプションで特定のテストだけ実行すると失敗する可能性
- ❌ pytest-xdist での並列実行ができない
- ❌ ランダム順序実行（`pytest --random-order`）ができない
- ❌ テストの独立性が保証されない

#### 4. **モジュールレベルのモデル定義**

**問題**: 一部のテストファイルでモジュールレベルでモデルを定義（過去）

**例** (Issue #021で修正済み):
```python
# test_date_type_comparison.py (修正前)
class TaskDateModel(BaseModel):  # モジュールレベル
    __tablename__ = 'task_date'
    # → インポート時に Base.metadata に登録される
```

**影響**:
- pytest がモジュールをインポートした瞬間に `Base.metadata` が汚染される
- テスト関数を実行しなくてもメタデータに影響

**現在の対処**:
- テスト関数内でローカル定義（Issue #021で修正）
- `extend_existing=True` を追加

---

## 期待される理想的な状態

### テストの独立性原則

✅ **完全な独立性**: 各テストは他のテストの存在を知らない
✅ **順序非依存**: どの順序で実行しても同じ結果
✅ **並列実行可能**: `pytest -n auto` で並列実行できる
✅ **ランダム順序対応**: `pytest --random-order` で実行できる
✅ **部分実行可能**: `pytest -k test_name` で単独実行できる

### 理想的なフィクスチャ設計

```python
@pytest.fixture
def isolated_environment():
    """完全に隔離されたテスト環境を提供"""
    # 1. 現在の状態を保存
    original_metadata = Base.metadata
    original_registry = Base.registry
    
    # 2. 新しい隔離環境を作成
    isolated_base = create_isolated_base()
    
    yield isolated_base
    
    # 3. 元の状態を復元（重要！）
    Base.metadata = original_metadata
    Base.registry = original_registry
```

---

## 提案される解決策

### Phase 1: isolated_mapper_registry の改善（高優先度）

**目的**: テスト後に元の状態を復元する

**実装案**:
```python
@pytest.fixture
def isolated_mapper_registry():
    """マッパーレジストリをクリアし、テスト後に復元"""
    # 1. 現在の状態をバックアップ
    original_tables = dict(Base.metadata.tables)
    original_mappers = list(Base.registry.mappers)
    
    # 2. クリア
    clear_mappers()
    Base.metadata.clear()
    
    yield
    
    # 3. 復元（重要！）
    clear_mappers()
    Base.metadata.clear()
    
    # 既存のテーブルを復元
    for table_name, table in original_tables.items():
        table.to_metadata(Base.metadata)
    
    # マッパーを再構築
    configure_mappers()
```

**メリット**:
- 他のテストへの影響を排除
- 実行順序非依存になる
- `test_00_migration_no_id.py` のリネームが不要になる

**デメリット**:
- 実装が複雑
- メタデータの完全な復元が難しい可能性
- パフォーマンスへの影響

**優先度**: 高

---

### Phase 2: 完全に隔離された Base の使用（根本的解決）

**目的**: グローバル `Base` に依存しない

**実装案**:
```python
from sqlalchemy.orm import declarative_base

@pytest.fixture
def isolated_base():
    """完全に隔離された Base を提供"""
    IsolatedBase = declarative_base()
    return IsolatedBase

# テストでの使用
def test_something(isolated_base):
    class TestModel(isolated_base):
        __tablename__ = 'test_model'
        id: Mapped[int] = mapped_column(primary_key=True)
    
    # このモデルはグローバル Base に影響しない
```

**メリット**:
- ✅ 完全な独立性
- ✅ 並列実行可能
- ✅ 順序非依存
- ✅ グローバルステート汚染なし

**デメリット**:
- 既存テストの大規模な書き換えが必要
- `BaseModel` の継承をどう扱うか（設計が必要）
- Alembic テストとの互換性を保つ必要

**優先度**: 中（Phase 1 の後）

---

### Phase 3: テスト実行順序の依存を排除

**目的**: `test_00_migration_no_id.py` のリネームを元に戻す

**実装**:
- Phase 1 または Phase 2 が完了すれば自動的に解決
- `test_00_migration_no_id.py` → `test_migration_no_id.py` へリネーム
- 実行順序に依存しないことを確認

**検証方法**:
```bash
# ランダム順序実行
pytest --random-order tests/behavior_tests/

# 並列実行
pytest -n auto tests/behavior_tests/

# 逆順実行（手動）
pytest tests/behavior_tests/test_unique_key_handling.py \
       tests/behavior_tests/test_migration_no_id.py
```

---

### Phase 4: モジュールレベル定義の完全排除（追加対策）

**目的**: pytest インポート時のメタデータ汚染を防ぐ

**ガイドライン**:
```python
# ❌ NG: モジュールレベル定義
class MyModel(BaseModel):
    __tablename__ = 'my_model'

# ✅ OK: フィクスチャで定義
@pytest.fixture
def my_model_class():
    class MyModel(BaseModel):
        __tablename__ = 'my_model'
        __table_args__ = {'extend_existing': True}
    return MyModel

# ✅ OK: テスト関数内で定義
def test_something():
    class MyModel(BaseModel):
        __tablename__ = 'my_model'
        __table_args__ = {'extend_existing': True}
    # テスト実行
```

**対象ファイル（確認必要）**:
- `tests/behavior_tests/test_00_migration_no_id.py` (モジュールレベル定義あり)
- 他のbehavior_testsファイル

---

## 影響範囲

### 修正が必要なファイル

#### Phase 1
- `tests/conftest.py` - `isolated_mapper_registry` の改善

#### Phase 2
- `tests/conftest.py` - `isolated_base` フィクスチャ追加
- `tests/behavior_tests/*.py` - 全ての behavior tests
- `tests/unit_tests/*.py` - Base 使用箇所の確認

#### Phase 3
- `tests/behavior_tests/test_00_migration_no_id.py` - リネーム
- `tests/conftest.py` - `behavior_test_modules` リスト更新

#### Phase 4
- `tests/behavior_tests/test_00_migration_no_id.py` - モデル定義をフィクスチャ化

---

## 実装計画

### Step 1: 現状の問題を詳細調査（1-2時間）

- [ ] すべてのテストファイルでモジュールレベル定義を確認
- [ ] `isolated_mapper_registry` の使用箇所をリスト化
- [ ] Base.metadata に依存するテストを特定
- [ ] 実行順序依存のテストを特定

### Step 2: Phase 1 実装（2-3時間）

- [ ] `isolated_mapper_registry` の改善実装
- [ ] 状態のバックアップ・復元ロジック
- [ ] 既存テストが壊れないことを確認
- [ ] ランダム順序実行テスト

### Step 3: Phase 1 検証（1時間）

- [ ] `pytest --random-order tests/behavior_tests/` が成功
- [ ] `pytest -k test_migration` が単独で成功
- [ ] 全テストが順序非依存であることを確認

### Step 4: Phase 3 実装（30分）

- [ ] `test_00_migration_no_id.py` → `test_migration_no_id.py` リネーム
- [ ] `conftest.py` 更新
- [ ] 検証

### Step 5: Phase 2 設計検討（必要に応じて）

- [ ] `isolated_base` の設計
- [ ] `BaseModel` との互換性検討
- [ ] プロトタイプ実装
- [ ] パフォーマンス測定

### Step 6: Phase 4 実装（必要に応じて）

- [ ] モジュールレベル定義をフィクスチャ化
- [ ] ガイドライン文書化

---

## テスト計画

### テストケース

#### 1. 実行順序非依存性

```bash
# 正順
pytest tests/behavior_tests/test_a.py tests/behavior_tests/test_b.py

# 逆順
pytest tests/behavior_tests/test_b.py tests/behavior_tests/test_a.py

# ランダム
pytest --random-order tests/behavior_tests/
```

**成功基準**: すべてのパターンで同じ結果

#### 2. 並列実行

```bash
pytest -n auto tests/behavior_tests/
```

**成功基準**: 並列実行でもすべてのテストがPASS

#### 3. 単独実行

```bash
pytest -k test_migration_without_id
```

**成功基準**: 単独実行でもPASS

#### 4. Base.metadata の汚染検証

```python
def test_metadata_isolation():
    """テスト前後で Base.metadata が変化しないことを確認"""
    initial_tables = set(Base.metadata.tables.keys())
    
    # isolated_mapper_registry を使用するテストを実行
    # ...
    
    final_tables = set(Base.metadata.tables.keys())
    assert initial_tables == final_tables
```

---

## 完了基準

### Phase 1 完了条件

- [x] `isolated_mapper_registry` が状態を復元する
- [x] ランダム順序実行が成功
- [x] 全テストが順序非依存

### Phase 3 完了条件

- [x] `test_migration_no_id.py` にリネーム完了
- [x] 実行順序に依存しない
- [x] CI/CD で安定動作

### 全体完了条件

- [x] すべてのテストが完全に独立
- [x] 並列実行が可能
- [x] ランダム順序実行が可能
- [x] ドキュメント更新（testing_guide.md）

---

## トレードオフと懸念事項

### パフォーマンス

**懸念**: 状態のバックアップ・復元により実行時間が増加する可能性

**対策**:
- ベンチマーク測定（Phase 1 実装前後）
- 許容範囲（現在 ~5秒、+1-2秒は許容）を定義
- 必要に応じて最適化

### 複雑性

**懸念**: メタデータの完全な復元は複雑

**対策**:
- 段階的実装（Phase 1 → Phase 2）
- 失敗時のフォールバック戦略
- 詳細なテストで検証

### 後方互換性

**懸念**: 既存テストが壊れる可能性

**対策**:
- 既存テストを壊さない実装を優先
- 段階的移行（Phase 2 は任意）
- 全テストを実行して検証

---

## 関連ドキュメント

- **Issue #021**: [completed/021_test_mapper_clear_interference.md](../completed/021_test_mapper_clear_interference.md) - 実行順序問題の対処
- **Issue #022**: [active/022_isolated_mapper_registry_improvement.md](active/022_isolated_mapper_registry_improvement.md) - isolated_mapper_registry の改善提案
- **Testing Guide**: [docs/guides/testing/testing_guide.md](../../guides/testing/testing_guide.md) - テスト戦略
- **Transaction Rollback Pattern**: Issue #009 で実装済み（高速化達成）

---

## 参考資料

### テストの独立性に関するベストプラクティス

1. **pytest ドキュメント**: [Good Integration Practices](https://docs.pytest.org/en/stable/goodpractices.html)
2. **SQLAlchemy Testing**: [Testing with SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
3. **Test Isolation Patterns**: Martin Fowler の "Test Isolation" 記事

---

**次のステップ**: Phase 1 の実装（`isolated_mapper_registry` の改善）から開始することを推奨。

---

最終更新: 2026-01-29
