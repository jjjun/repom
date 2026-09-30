# 論理削除（Soft Delete）ガイド

このガイドでは、repom の論理削除機能の使用方法を説明します。

## 目次

- [概要](#概要)
- [基本的な使い方](#基本的な使い方)
- [API リファレンス](#api-リファレンス)
- [非同期 Repository とセッション管理](#非同期-repository-とセッション管理)
- [使用例](#使用例)
- [マイグレーション](#マイグレーション)
- [ベストプラクティス](#ベストプラクティス)
- [トラブルシューティング](#トラブルシューティング)

---

## 概要

論理削除（Soft Delete）は、データベースレコードを物理的に削除せず、「削除済み」フラグを立てることでデータを保持する手法です。

### 主な利点

- **誤削除からの復元**: 削除されたデータを簡単に復元可能
- **監査証跡**: 削除履歴を保持できる
- **段階的削除**: 論理削除 → 一定期間保持 → 物理削除のフローを実現
- **参照整合性**: 外部キー制約を維持しながら削除状態を管理

### repom の論理削除機能

repom は以下の2つのコンポーネントで論理削除をサポートします：

1. **SoftDeletableMixin**: モデルに `deleted_at` カラムと削除操作メソッドを追加
2. **BaseRepository 拡張**: 削除済みレコードの自動フィルタリングと管理メソッド

---

## 基本的な使い方

### 1. モデルに Mixin を追加

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom import BaseModel, SoftDeletableMixin

class Article(BaseModel, SoftDeletableMixin):
    __tablename__ = "articles"
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(String)
```

これだけで、以下が自動的に追加されます：

- `deleted_at` カラム（`UTCDateTime` / `DateTime(timezone=True)`、インデックス付き）
- `soft_delete()` メソッド
- `restore()` メソッド
- `is_deleted` プロパティ

### 2. Repository での使用

```python
from repom import BaseRepository

repo = BaseRepository(Article)

# 論理削除
repo.soft_delete(article_id)

# 復元
repo.restore(article_id)

# 物理削除（完全削除）
repo.permanent_delete(article_id)
```

### 3. 自動フィルタリング

論理削除されたレコードは、デフォルトで自動的に除外されます：

```python
# 削除済みを除外（デフォルト）
active_articles = repo.find(limit=100)

# 削除済みも含める
all_articles = repo.find(include_deleted=True, limit=100)

# ID で取得（削除済みを除外）
article = repo.get_by_id(1)

# ID で取得（削除済みも含む）
article = repo.get_by_id(1, include_deleted=True)
```

`count()`、`get_all()`、`find_one()`、`find_by_ids()`、`get_by()` も
`include_deleted` を受け付けます。既定値は `False` です。`SoftDeletableMixin` を
持たないモデルでは、`find_deleted()` と `find_deleted_before()` は空リストを返します。

`remove(instance)` は `SoftDeletableMixin` を持つモデルに対しても物理削除します。
`bulk_delete()` は Mixin を持つモデルの該当行を論理削除し、Mixin を持たないモデルの
該当行を物理削除します。
`bulk_update()` は既定で論理削除済みの行を除外します。削除済みの行を復元するなど、
更新対象に含める場合は `include_deleted=True` を指定してください。

---

## API リファレンス

### SoftDeletableMixin

#### deleted_at: Mapped[datetime | None]

削除日時を記録するカラム。NULL の場合は削除されていません。

- **型**: `UTCDateTime` (`DateTime(timezone=True)`)
- **デフォルト**: `None`
- **インデックス**: あり

SQLite では保存時にタイムゾーン情報が保持されませんが、`UTCDateTime` が読み込み時に
UTC の `tzinfo` を付与するため、`deleted_at` は常に UTC-aware な datetime として返ります。

#### soft_delete() -> None

論理削除を実行します。`deleted_at` に現在時刻（UTC）を設定します。

```python
repo = BaseRepository(Article, session=session)
article = repo.get_by_id(1)
article.soft_delete()
session.commit()
```

**注意**: セッションのコミットは呼び出し側で行う必要があります。

この例の `session` は呼び出し側が管理する SQLAlchemy `Session` です。モデルの
メソッドを直接呼ぶ場合は Repository にこのセッションを渡してください。
セッションを渡さない Repository の取得結果は内部セッション終了時にデタッチされる
ため、この方法では変更が保存されません。

#### restore() -> None

削除を取り消します。`deleted_at` を NULL に戻します。

```python
repo = BaseRepository(Article, session=session)
article = repo.get_by_id(1, include_deleted=True)
if article and article.is_deleted:
    article.restore()
    session.commit()
```

#### is_deleted: bool (プロパティ)

削除済みかどうかを返します。

```python
if article.is_deleted:
    print("この記事は削除されています")
```

---

### BaseRepository メソッド

#### find(params=None, filters=None, include_deleted=False, **kwargs) -> List[T]

レコードを検索します。

**パラメータ**:
- `params`: `FilterParams` インスタンス（任意）
- `filters`: SQLAlchemy フィルタ条件のリスト
- `include_deleted`: 削除済みも含めるか（デフォルト: False）
- `**kwargs`: `offset`, `limit`, `order_by` などのオプション

```python
# 削除済みを除外
active = repo.find(limit=100)

# 削除済みも含む
all_items = repo.find(include_deleted=True, limit=100)

# 条件付き検索
published = repo.find(filters=[Article.status == 'published'], limit=100)
```

`include_deleted` は `count()`、`get_all()`、`find_one()`、`find_by_ids()`、
`get_by()`、`get_by_id()` でも利用できます。既定値は `False` です。

#### get_by_id(id, include_deleted=False) -> Optional[T]

ID でレコードを取得します。

**パラメータ**:
- `id`: レコードの ID
- `include_deleted`: 削除済みも含めるか（デフォルト: False）

```python
# 削除済みを除外
article = repo.get_by_id(1)

# 削除済みも含む
article = repo.get_by_id(1, include_deleted=True)
```

#### soft_delete(id) -> bool

論理削除を実行します。

Repository の `soft_delete()`、`restore()`、`permanent_delete()` は、内部セッションを
使う場合は commit し、`session=` で外部セッションが渡された場合は flush のみを
行います。外部セッションのトランザクションは呼び出し側が管理します。

**パラメータ**:
- `id`: 削除するレコードの ID

**戻り値**:
- `True`: 削除成功
- `False`: レコードが見つからない

**例外**:
- `ValueError`: モデルが SoftDeletableMixin を持たない場合

```python
if repo.soft_delete(1):
    print("削除成功")
else:
    print("レコードが見つかりません")
```

#### restore(id) -> bool

削除を復元します。

**パラメータ**:
- `id`: 復元するレコードの ID

**戻り値**:
- `True`: 復元成功
- `False`: 削除済みレコードが見つからない

```python
if repo.restore(1):
    print("復元成功")
```

#### permanent_delete(id) -> bool

物理削除（完全削除）を実行します。

**警告**: この操作は取り消せません。

**パラメータ**:
- `id`: 削除するレコードの ID

**戻り値**:
- `True`: 削除成功
- `False`: レコードが見つからない

```python
if repo.permanent_delete(1):
    print("物理削除完了")
```

#### find_deleted(filters=None, **kwargs) -> List[T]

削除済みレコードのみを取得します。

```python
deleted_articles = repo.find_deleted(limit=100)
print(f"{len(deleted_articles)} 件の削除済み記事")
```

#### find_deleted_before(before_date, **kwargs) -> List[T]

指定日時より前に削除されたレコードを取得します。

**パラメータ**:
- `before_date`: この日時より前に削除されたレコードを検索

```python
from datetime import datetime, timedelta, timezone

# 30日以上前に削除されたレコードを取得
threshold = datetime.now(timezone.utc) - timedelta(days=30)
old_deleted = repo.find_deleted_before(threshold)

# 物理削除
for item in old_deleted:
    repo.permanent_delete(item.id)
```

## 非同期 Repository とセッション管理

`AsyncBaseRepository` の削除操作と削除済みレコード検索には `await` が必要です。
`find_deleted()` と `find_deleted_before()` を含む `find_deleted*` メソッドも同様です。

```python
from datetime import datetime, timedelta, timezone

from repom import AsyncBaseRepository


async def manage_deleted_articles(article_id, async_session):
    repo = AsyncBaseRepository(Article, session=async_session)

    await repo.soft_delete(article_id)
    deleted_articles = await repo.find_deleted(limit=100)
    old_deleted = await repo.find_deleted_before(
        datetime.now(timezone.utc) - timedelta(days=30),
        limit=100,
    )
    await repo.restore(article_id)
    await repo.permanent_delete(article_id)
```

`session=` を省略すると Repository は内部セッションを使い、書き込みをコミット
します。外部の `Session` または `AsyncSession` を渡した場合、Repository は flush のみ
を行います。トランザクションの commit / rollback は呼び出し側が行います。モデルの
`soft_delete()` / `restore()` は属性を変更するだけなので、直接呼ぶ場合も外部
セッションを使ってください。

---

## 使用例

### 基本的な CRUD + 削除フロー

```python
from repom import BaseRepository
from myapp.models import Article

repo = BaseRepository(Article)

# 作成
article = Article(title="新しい記事", content="内容...")
repo.save(article)

# 読み取り
article = repo.get_by_id(1)

# 更新
article.title = "更新されたタイトル"
repo.save(article)

# 論理削除
repo.soft_delete(1)

# 削除済みは取得できない
article = repo.get_by_id(1)  # None

# 復元
repo.restore(1)

# 物理削除
repo.permanent_delete(1)
```

### FastAPI での使用

```python
from fastapi import APIRouter, HTTPException, Depends
from repom import BaseRepository
from myapp.models import Article

router = APIRouter()

@router.delete("/articles/{article_id}")
def soft_delete_article(article_id: int):
    """記事を論理削除"""
    repo = BaseRepository(Article)
    if repo.soft_delete(article_id):
        return {"success": True, "message": "記事を削除しました"}
    raise HTTPException(status_code=404, detail="記事が見つかりません")

@router.post("/articles/{article_id}/restore")
def restore_article(article_id: int):
    """削除した記事を復元"""
    repo = BaseRepository(Article)
    if repo.restore(article_id):
        return {"success": True, "message": "記事を復元しました"}
    raise HTTPException(status_code=404, detail="削除済み記事が見つかりません")

@router.get("/articles")
def list_articles(include_deleted: bool = False):
    """記事一覧を取得"""
    repo = BaseRepository(Article)
    articles = repo.find(include_deleted=include_deleted, limit=100)
    return [article.to_dict() for article in articles]
```

### バッチ処理での物理削除

```python
from datetime import datetime, timedelta, timezone
from repom import BaseRepository
from myapp.models import Article
import logging

logger = logging.getLogger(__name__)

def cleanup_old_deleted_articles():
    """30日以上前に削除された記事を物理削除"""
    repo = BaseRepository(Article)
    
    threshold = datetime.now(timezone.utc) - timedelta(days=30)
    old_deleted = repo.find_deleted_before(threshold)
    
    success_count = 0
    fail_count = 0
    
    for article in old_deleted:
        try:
            if repo.permanent_delete(article.id):
                success_count += 1
                logger.info(f"Permanently deleted article: {article.id}")
            else:
                fail_count += 1
        except Exception as e:
            fail_count += 1
            logger.error(f"Failed to delete article {article.id}: {e}")
    
    return {
        "total": len(old_deleted),
        "success": success_count,
        "failed": fail_count
    }
```

### ファイルも含めた削除処理（mine-py での例）

```python
from pathlib import Path
from repom import BaseRepository
from myapp.models import AssetItem
import logging

logger = logging.getLogger(__name__)

class AssetRepository(BaseRepository[AssetItem]):
    def permanent_delete_with_file(self, asset_id: int) -> bool:
        """物理ファイルも含めて削除"""
        asset = self.get_by_id(asset_id, include_deleted=True)
        if not asset:
            return False
        
        # 物理ファイル削除
        file_path = Path(asset.storage_path)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete file: {file_path}, {e}")
                return False
        
        # DB削除
        return self.permanent_delete(asset_id)
```

---

## マイグレーション

### repom 単体で使用する場合

マイグレーションファイルを自動生成します：

```bash
uv run alembic revision --autogenerate -m "add soft delete to articles"
```

生成されるマイグレーション例：

```python
def upgrade():
    op.add_column('articles', 
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_articles_deleted_at', 'articles', ['deleted_at'])

def downgrade():
    op.drop_index('ix_articles_deleted_at', 'articles')
    op.drop_column('articles', 'deleted_at')
```

適用：

```bash
uv run alembic upgrade head
```

### 外部プロジェクトで使用する場合

外部プロジェクト（例: mine-py）で使用する場合も同様です：

```bash
# mine-py/ ディレクトリで実行
uv run alembic revision --autogenerate -m "add soft delete to asset_items"
uv run alembic upgrade head
```

---

## ベストプラクティス

### 1. 論理削除 vs 物理削除の使い分け

**論理削除を使うべき場合**:
- ユーザーデータ（記事、コメント、アセットなど）
- 監査証跡が必要なデータ
- 誤削除からの復元が必要なデータ
- 外部キーで参照されているデータ

**物理削除を使うべき場合**:
- 一時データ（セッション、キャッシュなど）
- プライバシー法で削除が義務付けられているデータ（GDPR など）
- ディスク容量が逼迫している場合

### 2. 定期的なクリーンアップ

論理削除されたデータは蓄積するため、定期的な物理削除が推奨されます：

```python
# 毎日実行するバッチジョブ
def daily_cleanup():
    repos = [
        BaseRepository(Article),
        BaseRepository(Comment),
        BaseRepository(AssetItem),
    ]
    
    threshold = datetime.now(timezone.utc) - timedelta(days=30)
    
    for repo in repos:
        old_deleted = repo.find_deleted_before(threshold)
        for item in old_deleted:
            repo.permanent_delete(item.id)
```

### 3. 管理画面での確認

削除済みデータを管理画面で確認できるようにします：

```python
@router.get("/admin/deleted-articles")
def list_deleted_articles():
    """削除済み記事の管理画面"""
    repo = BaseRepository(Article)
    deleted = repo.find_deleted(order_by=Article.deleted_at.desc(), limit=100)
    return [
        {
            "id": article.id,
            "title": article.title,
            "deleted_at": article.deleted_at.isoformat(),
        }
        for article in deleted
    ]
```

`deleted_at` は `allowed_order_columns` に既定では含まれません。文字列でなく
`Article.deleted_at.desc()` のような SQLAlchemy のカラム式を渡すと、このカラムで
ソートできます。

### 4. ログ記録

削除・復元操作はログに記録します：

```python
import logging

logger = logging.getLogger(__name__)

def delete_article(article_id: int):
    repo = BaseRepository(Article)
    if repo.soft_delete(article_id):
        logger.info(f"Article {article_id} soft deleted by user {current_user.id}")
        return True
    return False
```

### 5. 外部キー制約

論理削除を使用する場合、外部キー制約は維持されます：

```python
class Comment(BaseModel, SoftDeletableMixin):
    __tablename__ = "comments"
    
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    content: Mapped[str] = mapped_column(String)
```

記事が論理削除されても、コメントは保持されます。
必要に応じて、コメントも連動して論理削除するロジックを実装できます。

---

## トラブルシューティング

### Q: 論理削除非対応モデルで soft_delete() を呼ぶとエラー

**エラー**:
```
ValueError: MyModel does not support soft delete. Add SoftDeletableMixin to the model.
```

**解決策**:
モデルに `SoftDeletableMixin` を追加してください：

```python
class MyModel(BaseModel, SoftDeletableMixin):
    # ...
```

### Q: find() で削除済みが取得されてしまう

**原因**: モデルが `SoftDeletableMixin` を継承していない

**確認方法**:
```python
print(hasattr(MyModel, 'deleted_at'))  # False の場合は Mixin がない
```

**解決策**:
モデル定義を確認し、`SoftDeletableMixin` を追加してください。

### Q: 既存データに deleted_at カラムを追加したい

**手順**:

1. モデルに Mixin を追加
2. マイグレーションファイル生成
3. マイグレーション実行

```bash
uv run alembic revision --autogenerate -m "add soft delete"
uv run alembic upgrade head
```

既存のレコードは `deleted_at = NULL`（削除されていない）として扱われます。

### Q: 物理削除と論理削除を間違えた

**論理削除を物理削除してしまった場合**:
- バックアップから復元する必要があります
- 定期的なバックアップを推奨します

**物理削除すべきところを論理削除してしまった場合**:
```python
# 後から物理削除できます
repo.permanent_delete(item_id)
```

### Q: パフォーマンスが低下した

**原因**: deleted_at にインデックスがない可能性

**確認**:
SQLite の場合:

```sql
PRAGMA index_list('articles');
```

結果に `ix_articles_deleted_at` が表示されることを確認します。

PostgreSQL の場合:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'articles'
  AND indexname = 'ix_articles_deleted_at';
```

**解決策**:
`SoftDeletableMixin` はデフォルトで `index=True` を設定していますが、
手動でマイグレーションした場合はインデックスを追加してください：

```python
def upgrade():
    op.create_index('ix_articles_deleted_at', 'articles', ['deleted_at'])
```

---

## 関連ドキュメント

- [BaseRepository ガイド](../repository/base_repository_guide.md) - Repository パターンの詳細
- [Testing ガイド](../testing/testing_guide.md) - テスト戦略

FastAPI 向けの Pydantic スキーマ自動生成は、利用側フレームワーク（fast-domain）に移管されました。

---

最終更新: 2025-12-10
