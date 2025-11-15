# SQLAlchemy 2.0 スタイルへの移行

## ステータス
- **段階**: 計画中
- **優先度**: 中
- **複雑度**: 中
- **作成日**: 2025-11-15

## 概要

repom プロジェクト全体を SQLAlchemy 2.0 の推奨スタイル（`Mapped[]` 型ヒント + `mapped_column()`）に移行する。これにより、型安全性の向上、エディタ補完の改善、将来のバージョン互換性を確保する。

## モチベーション

### 現在の問題点

1. **型チェックが効かない**: `Column()` では型情報が失われる
   ```python
   # ❌ 現在（型が Any として扱われる）
   value = Column(String(255), nullable=False)
   ```

2. **エディタ補完が不正確**: mypy/Pylance が正確な型を推論できない

3. **将来の非互換リスク**: SQLAlchemy 1.4 スタイルは将来的に非推奨になる可能性

4. **ドキュメントとの不一致**: 新しいガイドでは `Mapped[]` を推奨しているが、実装は古いスタイル

### SQLAlchemy 2.0 スタイルの利点

```python
# ✅ 新しいスタイル（型安全）
value: Mapped[str] = mapped_column(String(255))
page_id: Mapped[Optional[int]] = mapped_column(Integer)
posts: Mapped[List["Post"]] = relationship(back_populates="user")
```

**メリット**:
- ✅ 型チェックが効く（mypy/Pylance）
- ✅ エディタ補完が正確
- ✅ 実行前にタイポや型ミスを検出
- ✅ 可読性向上（型ヒントで意図が明確）
- ✅ SQLAlchemy 2.0+ の標準スタイル

## 影響範囲

### repom プロジェクト内

| ファイル | 箇所数 | 優先度 | 備考 |
|---------|--------|--------|------|
| `repom/models/sample.py` | 2 | 高 | サンプルモデル（ユーザー参照） |
| `repom/models/user_session.py` | 6 | 高 | サンプルモデル（ユーザー参照） |
| `repom/base_model.py` | 3 | **最重要** | すべてのモデルに影響 |
| `repom/base_model_auto.py` | 5+ | 高 | ドキュメントコメント |
| `tests/unit_tests/*.py` | 100+ | 中 | テストモデル |
| `tests/behavior_tests/*.py` | 20+ | 中 | テストモデル |

### 外部プロジェクト（consuming projects）

repom を使用しているすべてのプロジェクトで、以下の移行が必要：

1. **モデル定義の書き換え**
   - `Column()` → `mapped_column()`
   - 型ヒント追加（`Mapped[型]`, `Mapped[Optional[型]]`）
   - relationship に型ヒント追加（`Mapped["モデル名"]`）

2. **import 文の追加**
   ```python
   from sqlalchemy.orm import Mapped, mapped_column, relationship
   from typing import Optional, List
   ```

3. **カスタム型の使い方確認**
   - ListJSON, JSONEncoded などの型ヒント

## 実装計画

### Phase 1: repom コアの移行（最重要）

**目標**: repom 内部の基盤を SQLAlchemy 2.0 スタイルに移行

#### 1.1. BaseModel の修正

**ファイル**: `repom/base_model.py`

**変更内容**:
```python
from sqlalchemy.orm import Mapped, mapped_column

class BaseModel(DeclarativeBase):
    # ❌ 古いスタイル
    # cls.id = Column(Integer, primary_key=True)
    # cls.created_at = Column(AutoDateTime)
    # cls.updated_at = Column(AutoDateTime)
    
    # ✅ 新しいスタイル
    if cls.use_id:
        cls.id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    if cls.use_created_at:
        cls.created_at: Mapped[datetime] = mapped_column(AutoDateTime, init=False)
    if cls.use_updated_at:
        cls.updated_at: Mapped[datetime] = mapped_column(AutoDateTime, init=False)
```

**影響**: すべての repom モデルと consuming project のモデル

**テスト**: 既存のすべてのテストが通ることを確認

#### 1.2. サンプルモデルの修正

**ファイル**: `repom/models/sample.py`, `repom/models/user_session.py`

**変更内容**:
```python
# sample.py
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from datetime import date

class SampleModel(BaseModel):
    __tablename__ = get_plural_tablename(__file__)
    use_created_at = True

    value: Mapped[str] = mapped_column(String(255), default='')
    done_at: Mapped[Optional[date]] = mapped_column(Date)
```

```python
# user_session.py
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from datetime import datetime

class UserSession(BaseModelAuto, use_id=False):
    __tablename__ = 'user_sessions'

    # Composite primary key
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Session data
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime)
```

**影響**: ユーザーが参照するサンプルコード

**重要度**: 高（ユーザーがコピペして使用する可能性）

#### 1.3. BaseModelAuto のドキュメント更新

**ファイル**: `repom/base_model_auto.py`

**変更内容**: docstring 内の例を `Mapped[]` スタイルに更新

### Phase 2: テストコードの移行

**目標**: すべてのテストモデルを SQLAlchemy 2.0 スタイルに移行

**ファイル**: `tests/unit_tests/*.py`, `tests/behavior_tests/*.py`

**変更箇所**: 100+ 箇所

**方針**:
- 一括置換は避ける（テストの意図を保つため）
- ファイル単位で段階的に移行
- 各ファイル修正後にテスト実行して確認

**優先順位**:
1. `test_base_model_auto.py` - BaseModelAuto の機能テスト
2. `test_response_field.py` - レスポンススキーマ生成テスト
3. `test_response_schema_forward_refs.py` - 前方参照のテスト
4. その他のテストファイル

### Phase 3: ドキュメント整備

**目標**: すべてのドキュメントを SQLAlchemy 2.0 スタイルに統一

**対象ファイル**:
- `docs/guides/base_model_auto_guide.md`
- `docs/guides/repository_and_utilities_guide.md`
- `docs/guides/auto_import_models_guide.md`（新規作成済み）
- `README.md`
- `.github/copilot-instructions.md`

**変更内容**:
- すべてのコード例を `Mapped[]` スタイルに更新
- 移行ガイドセクションの追加
- ベストプラクティスの明記

### Phase 4: 外部プロジェクト移行ガイド作成

**目標**: consuming project が repom を SQLAlchemy 2.0 スタイルで使えるようにする

**成果物**: `docs/guides/migration_to_sqlalchemy_2_0.md`

**内容**:
1. **移行の必要性**
   - なぜ移行すべきか
   - 移行しない場合のリスク

2. **移行手順**
   - ステップバイステップガイド
   - Before/After のコード例
   - よくあるパターン集

3. **チェックリスト**
   - [ ] import 文を追加
   - [ ] Column → mapped_column に置換
   - [ ] 型ヒントを追加（Mapped[型]）
   - [ ] relationship に型ヒント追加
   - [ ] Optional フィールドに Optional[型] を使用
   - [ ] テスト実行

4. **トラブルシューティング**
   - よくあるエラーと解決方法
   - 型チェックエラーの対処

5. **段階的移行戦略**
   - 新しいモデルから採用
   - 既存モデルは徐々に移行
   - 混在期の注意点

### Phase 5: 外部プロジェクトの実移行

**目標**: 実際の consuming project を移行する

**対象**: repom を使用している既存プロジェクト（例: アニメデータベースプロジェクト）

**手順**:
1. Phase 4 の移行ガイドに従って移行
2. 移行中に発見した問題を移行ガイドにフィードバック
3. 移行完了後、ベストプラクティスをドキュメント化

## 実装上の注意点

### 1. BaseModel での動的カラム追加

**課題**: `__init_subclass__` で動的にカラムを追加する際、型ヒントをどう付けるか

```python
# 現在の実装
def __init_subclass__(cls, use_id=_UNSET, ...):
    if cls.use_id:
        cls.id = Column(Integer, primary_key=True)  # 動的に追加
```

**問題**: 型ヒントは静的に解決されるため、動的追加との相性が悪い

**解決策**:
- Option A: `__annotations__` を手動で更新
  ```python
  cls.id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
  cls.__annotations__['id'] = Mapped[int]
  ```

- Option B: stub ファイル (`.pyi`) で型定義
  ```python
  # base_model.pyi
  class BaseModel:
      id: Mapped[int]
      created_at: Mapped[datetime]
      updated_at: Mapped[datetime]
  ```

**推奨**: Option A（stub ファイルは管理が煩雑）

### 2. カスタム型との互換性

**課題**: ListJSON, JSONEncoded などのカスタム型で型ヒントをどうするか

```python
# 現在
studio_names = Column(ListJSON)

# 移行後の型ヒント
studio_names: Mapped[Optional[list]] = mapped_column(ListJSON)
# または
studio_names: Mapped[Optional[List[str]]] = mapped_column(ListJSON)
```

**推奨**: より具体的な型（`List[str]`, `Dict[str, Any]`）を使用

### 3. relationship の型ヒント

**重要**: 循環参照を避けるため、必ず文字列で前方参照

```python
# ✅ 正しい（文字列で前方参照）
posts: Mapped[List["Post"]] = relationship(back_populates="user")

# ❌ 間違い（循環参照が発生する可能性）
from models.post import Post
posts: Mapped[List[Post]] = relationship(back_populates="user")
```

### 4. 後方互換性

**方針**: 既存の consuming project が壊れないようにする

- repom 内部の変更は後方互換性を維持
- 新しいスタイルと古いスタイルの混在を許容（移行期間中）
- 非互換な変更は major version bump で導入

## 検証項目

### repom プロジェクト

- [ ] すべての unit tests が通る（151/153 → 153/153）
- [ ] すべての behavior tests が通る
- [ ] `poetry run alembic revision --autogenerate` が正常動作
- [ ] `poetry run db_create` が正常動作
- [ ] mypy でエラーが出ない（新規追加）

### 外部プロジェクト

- [ ] 既存のモデルが動作する（後方互換性）
- [ ] 新しいスタイルで書かれたモデルが動作する
- [ ] Alembic マイグレーションが正常生成される
- [ ] BaseRepository の操作が正常動作する
- [ ] get_response_schema() が正常動作する

## 完了条件

### Phase 1 完了条件
- [ ] `repom/base_model.py` が `Mapped[]` スタイル
- [ ] `repom/models/*.py` が `Mapped[]` スタイル
- [ ] すべてのテストが通る

### Phase 2 完了条件
- [ ] すべてのテストファイルが `Mapped[]` スタイル
- [ ] テストカバレッジが維持されている

### Phase 3 完了条件
- [ ] すべてのドキュメントが `Mapped[]` スタイル
- [ ] コード例がすべて最新

### Phase 4 完了条件
- [ ] 移行ガイド作成完了
- [ ] チェックリスト作成完了

### Phase 5 完了条件
- [ ] 実プロジェクトの移行完了
- [ ] 移行中の問題がドキュメント化されている

## タイムライン（目安）

| Phase | 作業内容 | 想定工数 | 優先度 |
|-------|---------|---------|--------|
| Phase 1 | repom コア移行 | 2-3時間 | 最重要 |
| Phase 2 | テスト移行 | 3-4時間 | 高 |
| Phase 3 | ドキュメント整備 | 2-3時間 | 高 |
| Phase 4 | 移行ガイド作成 | 2-3時間 | 高 |
| Phase 5 | 外部プロジェクト移行 | プロジェクト規模次第 | 中 |

**合計**: 10-15時間（Phase 1-4）

## リスク管理

### リスク 1: 型チェックの複雑化

**リスク**: 動的カラム追加と型ヒントの組み合わせで複雑化

**軽減策**: stub ファイルまたは `__annotations__` の手動更新

### リスク 2: 外部プロジェクトへの影響

**リスク**: repom のバージョンアップ時に consuming project が壊れる

**軽減策**: 
- 後方互換性を維持
- major version でのみ非互換変更
- 詳細な移行ガイド提供

### リスク 3: テストの網羅性

**リスク**: 移行後に見落としたバグが発生

**軽減策**: 
- 段階的な移行
- 各ステップでテスト実行
- Phase 5 で実プロジェクトで検証

## 関連ドキュメント

- **SQLAlchemy 2.0 Documentation**: https://docs.sqlalchemy.org/en/20/
- **Mapped and mapped_column()**: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#using-annotated-declarative-table
- **repom ガイド**:
  - `docs/guides/base_model_auto_guide.md`
  - `docs/guides/repository_and_utilities_guide.md`
  - `docs/guides/auto_import_models_guide.md`

## 参考資料

### SQLAlchemy 2.0 型ヒントの例

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from datetime import datetime, date

class User(BaseModelAuto):
    __tablename__ = 'users'
    
    # 必須フィールド（nullable=False）
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Optional フィールド（nullable=True）
    bio: Mapped[Optional[str]] = mapped_column(String(500))
    birth_date: Mapped[Optional[date]] = mapped_column(Date)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # カスタム型
    settings: Mapped[Optional[dict]] = mapped_column(JSON)
    tags: Mapped[Optional[list]] = mapped_column(ListJSON)
    
    # One-to-One
    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)
    
    # One-to-Many
    posts: Mapped[List["Post"]] = relationship(back_populates="author", cascade="all, delete-orphan")
    
    # Many-to-One
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'))
    group: Mapped["Group"] = relationship(back_populates="members")
```

---

**作成者**: AI Assistant  
**作成日**: 2025-11-15  
**最終更新**: 2025-11-15
