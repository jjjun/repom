# Issue #010: BaseModel への UUID サポート追加

**ステータス**: ✅ 完了

**作成日**: 2025-11-18

**完了日**: 2025-11-18

**優先度**: 中

---

## 問題の説明

repom を使用している外部プロジェクト（mine-py）で UUID を主キーとして使用したいという要望があった。現状では INTEGER 型の自動採番 id のみがサポートされており、UUID を使用する場合は手動で定義する必要があった。

**要望**:
- `use_id=True` と同様に、`use_uuid=True` パラメータで UUID 主キーを自動追加したい
- BaseRepository との互換性を保ちたい（カラム名は `id` のまま）
- 既存の use_id との排他制御が必要

---

## 提案される解決策

### 仕様

1. **パラメータ**: `use_uuid=True` を BaseModel に追加
2. **UUID 形式**: RFC 4122 準拠の UUID v4（36文字、ハイフン付き）
3. **カラム型**: `String(36)`
4. **カラム名**: `id`（BaseRepository 互換性のため）
5. **自動生成**: Python オブジェクト作成時に `str(uuid.uuid4())` で生成
6. **排他制御**: `use_uuid=True` と `use_id=True` は同時に指定不可

### 使用例

```python
class User(BaseModel, use_uuid=True):
    __tablename__ = 'users'
    
    name: Mapped[str] = mapped_column(String(100))

user = User(name='Alice')
print(user.id)  # '550e8400-e29b-41d4-a716-446655440000'

# BaseRepository も動作
repo = UserRepository(User)
retrieved = repo.get_by_id(user.id)
```

---

## 影響範囲

### 変更ファイル
- `repom/base_model.py`: use_uuid パラメータの実装
- `tests/unit_tests/test_base_model_uuid.py`: 包括的なテスト（17テスト）

### 影響を受ける機能
- ✅ 既存機能への影響なし（後方互換性保持）
- ✅ BaseRepository との完全な互換性
- ✅ to_dict(), update_from_dict() のサポート

---

## 実装内容

### BaseModel の変更

```python
import uuid
from sqlalchemy import String

class BaseModel(DeclarativeBase):
    def __init_subclass__(cls, use_uuid=_UNSET, ...):
        # 排他制御
        if cls.use_uuid and cls.use_id and cls.use_id is not _UNSET:
            raise ValueError('use_id と use_uuid は同時に True にできません')
        
        # use_uuid=True の場合、use_id を自動的に False に
        if cls.use_uuid:
            cls.use_id = False
            
            # UUID 主キーを追加
            cls.id: Mapped[str] = mapped_column(
                String(36),
                primary_key=True,
                default=lambda: str(uuid.uuid4())
            )
            
            # __init__ をオーバーライドして UUID を自動生成
            original_init = cls.__init__
            def __init__(self, *args, **kwargs):
                if 'id' not in kwargs:
                    kwargs['id'] = str(uuid.uuid4())
                original_init(self, *args, **kwargs)
            cls.__init__ = __init__
```

### テスト内容（17テスト）

1. **UUID 生成テスト** (4テスト)
   - UUID が自動生成されること
   - VARCHAR(36) 型であること
   - DB に保存できること
   - 各インスタンスで異なる UUID が生成されること

2. **排他制御テスト** (3テスト)
   - use_id と use_uuid の排他制御
   - use_id=True の動作確認
   - use_id=False, use_uuid=False の動作確認

3. **外部キー互換性テスト** (1テスト)
   - UUID id を外部キーで参照できること

4. **BaseRepository 互換性テスト** (3テスト)
   - get_by_id() が UUID で動作
   - データ作成と取得が動作
   - get_by() が UUID モデルで動作

5. **to_dict / update_from_dict テスト** (2テスト)
   - to_dict() が UUID id を含むこと
   - update_from_dict() が UUID id を保護すること

6. **created_at / updated_at テスト** (2テスト)
   - UUID モデルで created_at が動作
   - UUID モデルで updated_at が動作

7. **UUID 形式テスト** (2テスト)
   - UUID フォーマットが RFC 4122 準拠
   - UUID version が 4 であること

---

## テスト結果

### UUID テスト
```bash
poetry run pytest tests/unit_tests/test_base_model_uuid.py -v
# 17 passed in 0.25s
```

### 既存テスト（後方互換性確認）
```bash
poetry run pytest tests/unit_tests tests/behavior_tests -v
# 219 passed, 1 skipped in 19.98s
```

**結論**: 全テストパス、後方互換性完全保持

---

## ドキュメント更新

### 追加・更新したドキュメント

1. **system_columns_and_custom_types.md**
   - UUID サポートのセクションを追加
   - use_uuid=True の仕様説明
   - 排他制御の説明
   - 使用例とベストプラクティス
   - Integer vs UUID の使い分けガイド

2. **testing_guide.md**
   - 「repom プロジェクト内でのテスト作成ガイドライン」セクション追加
   - 独自の fixture を定義しない重要性
   - BaseRepository を使うテストの正しい書き方
   - get_by() の使い方
   - トラブルシューティング（"no such table" エラー）

---

## 学んだこと・改善点

### テスト作成での課題

1. **独自の fixture 定義による衝突**
   - 最初、テストファイル内で `db_engine`, `db_session` を定義
   - `conftest.py` の `db_test` と衝突し、"no such table" エラー
   - **解決**: 常に `conftest.py` の `db_test` を使用

2. **BaseRepository のセッション管理**
   - デフォルトの `db_session` を使うと、`db_test` のデータが見えない
   - **解決**: `MyRepository(MyModel, session=db_test)` とセッションを渡す

3. **get_by() の引数形式**
   - キーワード引数形式 `get_by(name='Alice')` は TypeError
   - **解決**: 位置引数形式 `get_by('name', 'Alice')` を使用

### testing_guide.md の改善

- 「repom プロジェクト内でのテスト作成」に特化したガイドラインを追加
- 今回の課題を元に、具体的な注意点とトラブルシューティングを記載
- 次回以降、同様の戸惑いを防げる内容に

---

## 使用例

### 基本的な使い方

```python
from repom.base_model import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

class User(BaseModel, use_uuid=True):
    __tablename__ = 'users'
    
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255))

# UUID が自動生成される
user = User(name='Alice', email='alice@example.com')
print(user.id)  # '550e8400-e29b-41d4-a716-446655440000'

# DB に保存
session.add(user)
session.commit()

# BaseRepository で取得
from repom.base_repository import BaseRepository

class UserRepository(BaseRepository[User]):
    pass

repo = UserRepository(User, session=session)
retrieved = repo.get_by_id(user.id)
assert retrieved.name == 'Alice'
```

### 外部キー参照

```python
class Post(BaseModel, use_uuid=True):
    __tablename__ = 'posts'
    
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('users.id')
    )
    title: Mapped[str] = mapped_column(String(200))

post = Post(user_id=user.id, title='Hello World')
session.add(post)
session.commit()
```

---

## 関連リソース

### コード
- `repom/base_model.py`: UUID サポート実装
- `tests/unit_tests/test_base_model_uuid.py`: UUID テスト

### ドキュメント
- `docs/guides/system_columns_and_custom_types.md`: UUID 仕様
- `docs/guides/testing_guide.md`: テスト作成ガイドライン

### コミット
- `feat(base_model): Add UUID support with use_uuid parameter` (2025-11-18)

---

**完了条件**: 
- ✅ UUID サポート実装完了
- ✅ 17テスト全パス
- ✅ 既存テスト全パス（後方互換性保持）
- ✅ ドキュメント更新完了
- ✅ コミット完了

**結論**: すべての要件を満たし、UUID 機能が正常に動作することを確認。ドキュメントも充実し、次回以降のテスト作成もスムーズに行えるようになった。
