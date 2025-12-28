# Issue #019: テストのフィクスチャ化によるコード品質向上

**ステータス**: 🟢 進行中

**作成日**: 2025-12-28

**優先度**: 中

---

## 問題の説明

現在の unit_tests では、多くのテストが**インラインデータ作成パターン**を使用しており、以下の問題があります:

### 現状の問題点

1. **コードの重複**
   - 各テストで同じデータ作成コードを繰り返している
   - DRY原則違反

2. **保守性の低下**
   - データ構造変更時に全テストを修正する必要がある
   - テストの数が増えるほど修正コストが増大

3. **可読性の低下**
   - テストロジックがデータ作成コードに埋もれる
   - テストの意図が不明瞭

### ❌ 問題のあるパターン例

```python
class TestSoftDelete:
    def test_soft_delete_sets_deleted_at(self, db_test):
        # 各テストでデータ作成を繰り返す
        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        
        item.soft_delete()
        assert item.is_deleted is True
    
    def test_restore_clears_deleted_at(self, db_test):
        # 同じデータ作成を再度行う
        item = SoftDeleteTestModel(name="test")
        db_test.add(item)
        db_test.commit()
        item.soft_delete()
        
        item.restore()
        assert item.is_deleted is False
```

**問題点:**
- データ作成が2回重複
- SoftDeleteTestModel の構造変更時、全テストを修正

---

## 提案される解決策

### ✅ フィクスチャパターンへの移行

```python
@pytest.fixture
def setup_soft_delete_item(db_test):
    """論理削除テスト用の共通データセットアップ"""
    item = SoftDeleteTestModel(name="test")
    db_test.add(item)
    db_test.commit()
    return item

class TestSoftDelete:
    def test_soft_delete_sets_deleted_at(self, setup_soft_delete_item):
        item = setup_soft_delete_item
        item.soft_delete()
        assert item.is_deleted is True
    
    def test_restore_clears_deleted_at(self, setup_soft_delete_item):
        item = setup_soft_delete_item
        item.soft_delete()
        
        item.restore()
        assert item.is_deleted is False
```

**メリット:**
- データ作成が1箇所に集約
- テストロジックが明確
- 保守性向上

---

## 対象ファイルと優先度

### 🔴 優先度: 高

#### 1. test_soft_delete.py (34テスト)

**現状:**
- 各テストで `SoftDeleteTestModel` および `NormalTestModel` を作成
- データ作成の重複が最も多い

**改善案:**
```python
@pytest.fixture
def setup_soft_delete_items(db_test):
    """論理削除対応モデルの共通データ"""
    repo = SoftDeleteRepository(session=db_test)
    item1 = repo.save(SoftDeleteTestModel(name='Item 1'))
    item2 = repo.save(SoftDeleteTestModel(name='Item 2'))
    item3 = repo.save(SoftDeleteTestModel(name='Item 3'))
    return {
        'repo': repo,
        'item1': item1,
        'item2': item2,
        'item3': item3,
    }

@pytest.fixture
def setup_normal_items(db_test):
    """論理削除非対応モデルの共通データ"""
    repo = BaseRepository[NormalTestModel](NormalTestModel, session=db_test)
    item1 = repo.save(NormalTestModel(name='Item 1'))
    return {
        'repo': repo,
        'item1': item1,
    }
```

**効果:**
- 34テスト中、推定20テスト以上で重複削減
- テストコード約30%削減見込み

---

### 🟡 優先度: 中

#### 2. test_save_for_creation.py (4テスト)

**現状:**
- 各テストで `SaveCreationTestModel` を作成
- テストケースごとに異なるデータパターン

**改善案:**
```python
@pytest.fixture
async def setup_save_repo(async_db_test):
    """リポジトリのみをフィクスチャ化"""
    return AsyncSaveRepository(session=async_db_test)

# 各テストはデータ作成を自身で行う（パターンが異なるため）
@pytest.mark.asyncio
async def test_save_method_for_new_entity_creation(self, setup_save_repo):
    repo = setup_save_repo
    model = SaveCreationTestModel(name='New')
    saved = await repo.save(model)
    # ...
```

**効果:**
- リポジトリ初期化の重複削減
- データパターンの柔軟性は維持

---

#### 3. test_refresh_behavior.py (4テスト)

**現状:**
- 各テストで `TestRefreshModel` を作成

**改善案:**
```python
@pytest.fixture
def setup_refresh_repo(db_test):
    """リポジトリのみをフィクスチャ化"""
    return RefreshRepository(session=db_test)
```

**効果:**
- テスト数が少ないため、効果は限定的
- 統一感のため実施推奨

---

### 🟢 優先度: 低（対象外）

以下のテストはフィクスチャ化**不要**と判断:

#### test_repository_init_pattern.py
- 理由: 異なる初期化パターンを検証するため、個別セットアップが必須

#### test_flush_refresh_pattern.py
- 理由: flush/refresh の動作検証のため、個別セットアップが必須

---

## 実装計画

### Phase 1: 高優先度テストのリファクタリング

#### ステップ1: test_soft_delete.py の修正

1. **フィクスチャ定義**
   ```python
   @pytest.fixture
   def setup_soft_delete_items(db_test):
       """論理削除対応モデルの共通データ"""
       # ...
   
   @pytest.fixture
   def setup_normal_items(db_test):
       """論理削除非対応モデルの共通データ"""
       # ...
   ```

2. **テストクラス修正**
   - `TestSoftDeletableMixin` → `setup_soft_delete_items` 使用
   - `TestBaseRepositorySoftDelete` → `setup_soft_delete_items` 使用
   - `TestSoftDeleteEdgeCases` → 必要に応じてフィクスチャ使用

3. **動作確認**
   ```bash
   poetry run pytest tests/unit_tests/test_soft_delete.py -v
   ```

4. **コミット**
   ```
   refactor(test): Use fixtures in test_soft_delete.py
   ```

#### ステップ2: test_save_for_creation.py の修正

1. **リポジトリフィクスチャ定義**
2. **テスト修正**
3. **動作確認**
4. **コミット**

#### ステップ3: test_refresh_behavior.py の修正

1. **リポジトリフィクスチャ定義**
2. **テスト修正**
3. **動作確認**
4. **コミット**

---

### Phase 2: 検証とドキュメント更新

1. **全テスト実行**
   ```bash
   poetry run pytest tests/unit_tests -v
   ```

2. **fixture_guide.md に実例追加**
   - test_soft_delete.py の実装例をリンク
   - フィクスチャ設計のベストプラクティスを追記

3. **Issue クローズ**
   - 完了報告
   - `docs/issue/completed/019_refactor_tests_to_use_fixtures.md` へ移動

---

## テスト計画

### 検証項目

1. **機能テスト**
   - 全テストが引き続きパスすること
   - テストの意図が変わっていないこと

2. **パフォーマンステスト**
   - テスト実行時間が大幅に増加していないこと
   - fixture の scope が適切に設定されていること

3. **可読性テスト**
   - テストコードが簡潔になっていること
   - フィクスチャの目的が明確であること

---

## 期待される効果

### コード品質向上

- **DRY原則遵守**: データ作成ロジックの一元化
- **保守性向上**: データ構造変更時の修正箇所が1箇所
- **可読性向上**: テストロジックとデータ作成の分離

### 定量的効果（推定）

- **test_soft_delete.py**: 約100行削減（30%削減）
- **全体**: 約150行削減（15%削減）
- **修正時間**: データ構造変更時の修正時間 70%削減

---

## 関連リソース

### ドキュメント
- [docs/guides/testing/fixture_guide.md](../../guides/testing/fixture_guide.md) - フィクスチャガイド（新規作成）
- [docs/guides/testing/testing_guide.md](../../guides/testing/testing_guide.md) - テスト戦略ガイド

### 実装例
- [tests/unit_tests/test_repository_default_order_by.py](../../../tests/unit_tests/test_repository_default_order_by.py) - 同期フィクスチャの例
- [tests/unit_tests/test_async_repository_default_order_by.py](../../../tests/unit_tests/test_async_repository_default_order_by.py) - 非同期フィクスチャの例

### 参考資料
- [pytest fixtures 公式ドキュメント](https://docs.pytest.org/en/stable/fixture.html)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)

---

## 進捗状況

### ✅ 完了

- [x] 問題調査と分析
- [x] フィクスチャガイド作成（fixture_guide.md）
- [x] test_async_repository_default_order_by.py のフィクスチャ化（参考実装）
- [x] Issue 作成

### 🚧 進行中

- [ ] test_soft_delete.py のリファクタリング
- [ ] test_save_for_creation.py のリファクタリング
- [ ] test_refresh_behavior.py のリファクタリング
- [ ] 全テスト検証
- [ ] ドキュメント更新

---

## 注意事項

### フィクスチャ設計の原則

1. **scope='function' を基本とする**
   - テスト間の独立性を保つ
   - Transaction Rollback パターンと相性が良い

2. **辞書で返す**
   - `return {'repo': repo, 'item1': item1, ...}`
   - キーで明確にアクセス可能

3. **非同期フィクスチャは autouse=False**
   - pytest-asyncio の制約
   - 各テストで明示的に受け取る

4. **docstring を必ず書く**
   - フィクスチャの目的とデータ構造を明記
   - 他の開発者が理解しやすく

---

最終更新: 2025-12-28
