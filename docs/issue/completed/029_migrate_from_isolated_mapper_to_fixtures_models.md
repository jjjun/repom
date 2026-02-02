# Issue #029: isolated_mapper_registry から tests/fixtures/models への移行

**ステータス**: ✅ 完了

**作成日**: 2026-02-02

**完了日**: 2026-02-02

**優先度**: 中

**複雑度**: 中

**関連 Issue**: #028 (テストアーキテクチャの複雑さ改善)

---

## 📋 問題の説明

現在の repom のテストシステムは、`isolated_mapper_registry` フィクスチャと `tests/fixtures/models/` の2つのモデル定義方法が混在しており、複雑性が増しています。

### 現状の問題点

1. **2つのモデル定義パターンが混在**
   - `isolated_mapper_registry` を使用してテスト関数内でモデルを定義
   - `tests/fixtures/models/` で事前定義されたモデルを使用

2. **`isolated_mapper_registry` の複雑性**
   - マッパーのクリア・再構築が必要
   - テスト間の干渉リスク
   - SQLAlchemy 内部 API への依存

3. **保守コストが高い**
   - 新規開発者がどちらを使うべきか迷う
   - ドキュメントが分散している
   - テストの可読性が低下

---

## 🔍 使用状況の調査結果

### `isolated_mapper_registry` の使用箇所

#### 1. **conftest.py** (フィクスチャ定義)
- `tests/conftest.py:129` - フィクスチャ定義

#### 2. **test_type_checking_detailed.py** (2箇所)
```python
def test_sqlalchemy_relationship_lazy_resolution(isolated_mapper_registry)
def test_actual_failure_scenario(isolated_mapper_registry)
```

**目的**: TYPE_CHECKING ブロックのテスト
- SQLAlchemy の前方参照解決を検証
- テスト関数内で動的にモデルを定義する必要がある

**移行可能性**: ❌ **不可** - これらは `isolated_mapper_registry` が必須

#### 3. **test_type_checking_import_order.py** (2箇所)
```python
def test_type_checking_with_alphabetical_import_order(isolated_mapper_registry)
def test_type_checking_with_manual_import_order(isolated_mapper_registry)
```

**目的**: TYPE_CHECKING とインポート順序の検証
- auto_import_models のインポート順序を検証
- テスト関数内で動的にモデルを定義

**移行可能性**: ❌ **不可** - これらも `isolated_mapper_registry` が必須

#### 4. **test_unique_key_handling.py** (コメントのみ)
```python
# This will be handled by the module reload in isolated_mapper_registry
```

**移行可能性**: ✅ **可能** - コメントのみなので影響なし

---

## 📊 移行計画の全体像

### Phase 1: 構造の準備 ✅ **完了**

- ✅ `tests/fixtures/models/` 構造を作成
- ✅ User, Post, Parent, Child モデルを定義
- ✅ `conftest.py` を更新してテストモデルをインポート
- ✅ 動作確認テスト (`test_fixtures_models.py`) を作成
- ✅ 603 tests passing

### Phase 2: ドキュメント整理 ✅ **完了**

#### Step 1: ドキュメント削除
- ✅ `docs/guides/testing/isolated_mapper_fixture.md` を削除
- ✅ `docs/issue/active/022_isolated_mapper_registry_improvement.md` を completed へ移動
- ✅ `docs/guides/testing/README.md` を更新

#### Step 2: `conftest.py` の更新
- ✅ `isolated_mapper_registry` フィクスチャの docstring を更新
- 「TYPE_CHECKING テスト専用」と明記

### Phase 3: 既存テストの分析 ✅ **完了**

**結論**: 
- **移行対象なし** - 全ての `isolated_mapper_registry` 使用は TYPE_CHECKING テスト
- これらは動的なモデル定義が必須のため、`isolated_mapper_registry` を維持

### Phase 4: 最終クリーンアップ ✅ **完了**

- ✅ `isolated_mapper_registry` を TYPE_CHECKING テスト専用として明確化
- ✅ ドキュメントで使い分けを明記

---

## ✅ 提案される解決策

### アプローチ: 役割の明確化

**`isolated_mapper_registry` を削除せず、役割を明確化する**

#### 1. **tests/fixtures/models/** (推奨)
**用途**: 通常のテスト
- 再利用可能なモデル
- CRUD 操作のテスト
- リレーションシップのテスト

**例**:
```python
from tests.fixtures.models import User, Post

def test_user_repository(db_test):
    user = User(name="Alice", email="alice@example.com")
    # ...
```

#### 2. **isolated_mapper_registry** (特殊ケースのみ)
**用途**: TYPE_CHECKING ブロックのテスト、動的モデル定義が必要なテスト
- 前方参照のテスト
- インポート順序の検証
- マッパー動作の検証

**例**:
```python
def test_type_checking(isolated_mapper_registry, db_test):
    # テスト関数内で動的にモデルを定義
    class TempModel(BaseModel):
        __tablename__ = 'temp'
        name: Mapped[str]
    # ...
```

---

## 📝 実装計画

### ✅ Phase 1: 完了 (2026-02-02)

- [x] `tests/fixtures/models/` 構造作成
- [x] 基本モデル (User, Post, Parent, Child) 定義
- [x] `conftest.py` 更新
- [x] 動作確認テスト作成
- [x] 603 tests passing 確認

### 🟡 Phase 2: ドキュメント整理 (次のステップ)

#### Step 2-1: ドキュメント削除
```bash
# 削除対象
git rm docs/guides/testing/isolated_mapper_fixture.md
git mv docs/issue/active/022_isolated_mapper_registry_improvement.md \
       docs/issue/completed/022_isolated_mapper_registry_improvement.md
```

#### Step 2-2: README 更新
- `docs/guides/testing/README.md` から isolated_mapper_fixture.md への言及を削除
- `tests/fixtures/models/` の使い方を追加

#### Step 2-3: conftest.py の docstring 更新
```python
@pytest.fixture
def isolated_mapper_registry(db_test):
    """TYPE_CHECKING テスト専用フィクスチャ

    ⚠️ 注意: このフィクスチャは TYPE_CHECKING ブロックのテストなど、
    動的にモデルを定義する必要がある特殊なケースでのみ使用してください。

    通常のテストでは tests/fixtures/models/ のモデルを使用してください。
    
    ...
    """
```

### 🟢 Phase 3: テスト方針の文書化

#### Step 3-1: testing_guide.md の更新
`docs/guides/testing/testing_guide.md` に以下を追加：

```markdown
## テストモデルの使い分け

### 推奨: tests/fixtures/models/ のモデルを使用

通常のテストでは、事前定義されたモデルを使用します：

\`\`\`python
from tests.fixtures.models import User, Post, Parent, Child

def test_user_crud(db_test):
    user = User(name="Alice", email="alice@example.com")
    # ...
\`\`\`

### 特殊ケース: isolated_mapper_registry

以下のような特殊なケースでのみ使用：
- TYPE_CHECKING ブロックの動作検証
- SQLAlchemy マッパーの動作検証
- インポート順序の検証

\`\`\`python
def test_type_checking(isolated_mapper_registry, db_test):
    class TempModel(BaseModel):
        __tablename__ = 'temp'
        name: Mapped[str]
    # ...
\`\`\`
```

### ✅ Phase 4: 最終確認

- [x] 全テストが passing
- [x] ドキュメントが更新されている
- [x] 新規開発者が迷わない構造になっている

---

## 🎯 完了基準

### 必須
- [x] `tests/fixtures/models/` 構造が作成されている
- [x] 603 tests passing (Phase 1)
- [x] `isolated_mapper_fixture.md` が削除されている
- [x] `testing_guide.md` に使い分けガイドが追加されている
- [x] `conftest.py` の docstring が更新されている
- [x] 全テストが passing

### 任意
- [ ] 新しいモデルを追加した場合、それらも動作確認済み

---

## 📊 影響範囲

### 変更対象ファイル

#### ドキュメント
- `docs/guides/testing/isolated_mapper_fixture.md` - 削除
- `docs/guides/testing/README.md` - 更新
- `docs/guides/testing/testing_guide.md` - 更新（使い分けガイド追加）
- `docs/issue/active/022_isolated_mapper_registry_improvement.md` - completed へ移動

#### コード
- `tests/conftest.py` - docstring 更新
- `tests/fixtures/models/` - 既存（変更なし）

#### テスト
- **変更なし** - 既存のテストは全て維持

---

## 🚀 次のアクション

### 即座に実施可能（Phase 2）

1. **ドキュメント削除**
   ```bash
   git rm docs/guides/testing/isolated_mapper_fixture.md
   git mv docs/issue/active/022_isolated_mapper_registry_improvement.md \
          docs/issue/completed/022_isolated_mapper_registry_improvement.md
   ```

2. **README 更新**
   - `docs/guides/testing/README.md` を更新

3. **conftest.py の docstring 更新**
   - 「TYPE_CHECKING テスト専用」と明記

4. **testing_guide.md の更新**
   - 使い分けガイドを追加

5. **テスト実行**
   ```bash
   poetry run pytest tests/unit_tests tests/behavior_tests -v
   ```

6. **Git コミット**
   ```bash
   git add docs/ tests/conftest.py
   git commit -m "docs(testing): Clarify isolated_mapper_registry usage and document tests/fixtures/models

   - Remove isolated_mapper_fixture.md (outdated, overly complex)
   - Update conftest.py docstring (TYPE_CHECKING tests only)
   - Update testing_guide.md with model usage guidelines
   - Move Issue #022 to completed (decided not to implement)
   - Clear separation: tests/fixtures/models (recommended) vs isolated_mapper_registry (special cases only)"
   ```

---

## 📝 関連ドキュメント

- **前提 Issue**: [#028 テストアーキテクチャの複雑さ改善](028_test_architecture_complexity.md)
- **完了予定 Issue**: [#022 isolated_mapper_registry の設計改善](022_isolated_mapper_registry_improvement.md) → completed へ
- **ガイド**: `docs/guides/testing/testing_guide.md`
- **既存構造**: `tests/fixtures/models/`

---

## 🔄 進捗ログ

### 2026-02-02 (Phase 1 完了)
- ✅ `tests/fixtures/models/` 構造作成
- ✅ User, Post, Parent, Child モデル定義
- ✅ `conftest.py` 更新
- ✅ `test_fixtures_models.py` 作成
- ✅ 603 tests passing 確認
- ✅ Git コミット完了

### 2026-02-02 (Phase 2 完了)
- ✅ 使用状況調査完了
- ✅ 移行計画の Issue 化完了
- ✅ ドキュメント整理完了
  - isolated_mapper_fixture.md 削除（360行削減）
  - Issue #022 を completed へ移動
  - README.md 更新（Quick Start 追加）
  - conftest.py docstring 更新
  - testing_guide.md 更新（使い分けガイド追加）
- ✅ 603 tests passing
- ✅ Git コミット完了

### 2026-02-02 (Phase 3-4 完了、Issue #029 完了)
- ✅ 最終確認完了
  - isolated_mapper_registry 使用箇所: 4件（すべて TYPE_CHECKING テスト）
  - tests/fixtures/models/ 提供完了（User, Post, Parent, Child）
  - 役割分担が明確化
- ✅ Issue #029 を completed へ移動

---

**最終更新**: 2026-02-02

**完了**: 2026-02-02
