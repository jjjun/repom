# 論理削除�E�Eoft Delete�E�ガイチE

こ�Eガイドでは、repom の論理削除機�Eの使用方法を説明します、E

## 目次

- [概要](#概要E
- [基本皁E��使ぁE��](#基本皁E��使ぁE��)
- [API リファレンス](#api-リファレンス)
- [使用例](#使用侁E
- [マイグレーション](#マイグレーション)
- [ベスト�EラクチE��ス](#ベスト�EラクチE��ス)
- [トラブルシューチE��ング](#トラブルシューチE��ング)

---

## 概要E

論理削除�E�Eoft Delete�E��E、データベ�Eスレコードを物琁E��に削除せず、「削除済み」フラグを立てることでチE�Eタを保持する手法です、E

### 主な利点

- **誤削除からの復允E*: 削除されたデータを簡単に復允E��能
- **監査証跡**: 削除履歴を保持できる
- **段階的削除**: 論理削除 ↁE一定期間保持 ↁE物琁E��除のフローを実現
- **参�E整合性**: 外部キー制紁E��維持しながら削除状態を管琁E

### repom の論理削除機�E

repom は以下�E2つのコンポ�Eネントで論理削除をサポ�Eトします！E

1. **SoftDeletableMixin**: モチE��に `deleted_at` カラムと削除操作メソチE��を追加
2. **BaseRepository 拡張**: 削除済みレコード�E自動フィルタリングと管琁E��ソチE��

---

## 基本皁E��使ぁE��

### 1. モチE��に Mixin を追加

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom.models import BaseModelAuto, SoftDeletableMixin

class Article(BaseModelAuto, SoftDeletableMixin):
    __tablename__ = "articles"
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(String)
```

これだけで、以下が自動的に追加されます！E

- `deleted_at` カラム�E�EateTime(timezone=True)、インチE��クス付き�E�E
- `soft_delete()` メソチE��
- `restore()` メソチE��
- `is_deleted` プロパティ

### 2. Repository での使用

```python
from repom import BaseRepository

repo = BaseRepository(Article)

# 論理削除
repo.soft_delete(article_id)

# 復允E
repo.restore(article_id)

# 物琁E��除�E�完�E削除�E�E
repo.permanent_delete(article_id)
```

### 3. 自動フィルタリング

論理削除されたレコード�E、デフォルトで自動的に除外されます！E

```python
# 削除済みを除外（デフォルト！E
active_articles = repo.find()

# 削除済みも含める
all_articles = repo.find(include_deleted=True)

# ID で取得（削除済みを除外！E
article = repo.get_by_id(1)

# ID で取得（削除済みも含む�E�E
article = repo.get_by_id(1, include_deleted=True)
```

---

## API リファレンス

### SoftDeletableMixin

#### deleted_at: Mapped[datetime | None]

削除日時を記録するカラム、EULL の場合�E削除されてぁE��せん、E

- **垁E*: `DateTime(timezone=True)`
- **チE��ォルチE*: `None`
- **インチE��クス**: あり

#### soft_delete() -> None

論理削除を実行します。`deleted_at` に現在時刻�E�ETC�E�を設定します、E

```python
article = repo.get_by_id(1)
article.soft_delete()
session.commit()
```

**注愁E*: セチE��ョンのコミット�E呼び出し�Eで行う忁E��があります、E

#### restore() -> None

削除を取り消します。`deleted_at` めENULL に戻します、E

```python
article = repo.get_by_id(1, include_deleted=True)
if article and article.is_deleted:
    article.restore()
    session.commit()
```

#### is_deleted: bool (プロパティ)

削除済みかどぁE��を返します、E

```python
if article.is_deleted:
    print("こ�E記事�E削除されてぁE��ぁE)
```

---

### BaseRepository メソチE��

#### find(filters=None, include_deleted=False, **kwargs) -> List[T]

レコードを検索します、E

**パラメータ**:
- `filters`: SQLAlchemy フィルタ条件のリスチE
- `include_deleted`: 削除済みも含めるか（デフォルチE False�E�E
- `**kwargs`: `offset`, `limit`, `order_by` などのオプション

```python
# 削除済みを除夁E
active = repo.find()

# 削除済みも含む
all_items = repo.find(include_deleted=True)

# 条件付き検索
published = repo.find(filters=[Article.status == 'published'])
```

#### get_by_id(id, include_deleted=False) -> Optional[T]

ID でレコードを取得します、E

**パラメータ**:
- `id`: レコード�E ID
- `include_deleted`: 削除済みも含めるか（デフォルチE False�E�E

```python
# 削除済みを除夁E
article = repo.get_by_id(1)

# 削除済みも含む
article = repo.get_by_id(1, include_deleted=True)
```

#### soft_delete(id) -> bool

論理削除を実行します、E

**パラメータ**:
- `id`: 削除するレコード�E ID

**戻り値**:
- `True`: 削除成功
- `False`: レコードが見つからなぁE

**例夁E*:
- `ValueError`: モチE��ぁESoftDeletableMixin を持たなぁE��吁E

```python
if repo.soft_delete(1):
    print("削除成功")
else:
    print("レコードが見つかりません")
```

#### restore(id) -> bool

削除を復允E��ます、E

**パラメータ**:
- `id`: 復允E��るレコード�E ID

**戻り値**:
- `True`: 復允E�E劁E
- `False`: 削除済みレコードが見つからなぁE

```python
if repo.restore(1):
    print("復允E�E劁E)
```

#### permanent_delete(id) -> bool

物琁E��除�E�完�E削除�E�を実行します、E

**警呁E*: こ�E操作�E取り消せません、E

**パラメータ**:
- `id`: 削除するレコード�E ID

**戻り値**:
- `True`: 削除成功
- `False`: レコードが見つからなぁE

```python
if repo.permanent_delete(1):
    print("物琁E��除完亁E)
```

#### find_deleted(**kwargs) -> List[T]

削除済みレコード�Eみを取得します、E

```python
deleted_articles = repo.find_deleted()
print(f"{len(deleted_articles)} 件の削除済み記亁E)
```

#### find_deleted_before(before_date, **kwargs) -> List[T]

持E��日時より前に削除されたレコードを取得します、E

**パラメータ**:
- `before_date`: こ�E日時より前に削除されたレコードを検索

```python
from datetime import datetime, timedelta, timezone

# 30日以上前に削除されたレコードを取征E
threshold = datetime.now(timezone.utc) - timedelta(days=30)
old_deleted = repo.find_deleted_before(threshold)

# 物琁E��除
for item in old_deleted:
    repo.permanent_delete(item.id)
```

---

## 使用侁E

### 基本皁E�� CRUD + 削除フロー

```python
from repom import BaseRepository
from myapp.models import Article

repo = BaseRepository(Article)

# 作�E
article = Article(title="新しい記亁E, content="冁E��...")
repo.save(article)

# 読み取り
article = repo.get_by_id(1)

# 更新
article.title = "更新されたタイトル"
repo.save(article)

# 論理削除
repo.soft_delete(1)

# 削除済みは取得できなぁE
article = repo.get_by_id(1)  # None

# 復允E
repo.restore(1)

# 物琁E��除
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
    """削除した記事を復允E""
    repo = BaseRepository(Article)
    if repo.restore(article_id):
        return {"success": True, "message": "記事を復允E��ました"}
    raise HTTPException(status_code=404, detail="削除済み記事が見つかりません")

@router.get("/articles")
def list_articles(include_deleted: bool = False):
    """記事一覧を取征E""
    repo = BaseRepository(Article)
    articles = repo.find(include_deleted=include_deleted)
    return [article.to_dict() for article in articles]
```

### バッチ�E琁E��の物琁E��除

```python
from datetime import datetime, timedelta, timezone
from repom import BaseRepository
from myapp.models import Article
import logging

logger = logging.getLogger(__name__)

def cleanup_old_deleted_articles():
    """30日以上前に削除された記事を物琁E��除"""
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

### ファイルも含めた削除処琁E��Eine-py での例！E

```python
from pathlib import Path
from repom import BaseRepository
from myapp.models import AssetItem
import logging

logger = logging.getLogger(__name__)

class AssetRepository(BaseRepository[AssetItem]):
    def permanent_delete_with_file(self, asset_id: int) -> bool:
        """物琁E��ァイルも含めて削除"""
        asset = self.get_by_id(asset_id, include_deleted=True)
        if not asset:
            return False
        
        # 物琁E��ァイル削除
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

### repom 単体で使用する場吁E

マイグレーションファイルを�E動生成します！E

```bash
poetry run alembic revision --autogenerate -m "add soft delete to articles"
```

生�Eされる�Eイグレーション例！E

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

適用�E�E

```bash
poetry run alembic upgrade head
```

### 外部プロジェクトで使用する場吁E

外部プロジェクト（侁E mine-py�E�で使用する場合も同様です！E

```bash
# mine-py/ チE��レクトリで実衁E
poetry run alembic revision --autogenerate -m "add soft delete to asset_items"
poetry run alembic upgrade head
```

---

## ベスト�EラクチE��ス

### 1. 論理削除 vs 物琁E��除の使ぁE�EぁE

**論理削除を使ぁE��き場吁E*:
- ユーザーチE�Eタ�E�記事、コメント、アセチE��など�E�E
- 監査証跡が忁E��なチE�Eタ
- 誤削除からの復允E��忁E��なチE�Eタ
- 外部キーで参�EされてぁE��チE�Eタ

**物琁E��除を使ぁE��き場吁E*:
- 一時データ�E�セチE��ョン、キャチE��ュなど�E�E
- プライバシー法で削除が義務付けられてぁE��チE�Eタ�E�EDPR など�E�E
- チE��スク容量が逼迫してぁE��場吁E

### 2. 定期皁E��クリーンアチE�E

論理削除されたデータは蓁E��するため、定期皁E��物琁E��除が推奨されます！E

```python
# 毎日実行するバチE��ジョチE
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

### 3. 管琁E��面での確誁E

削除済みチE�Eタを管琁E��面で確認できるようにします！E

```python
@router.get("/admin/deleted-articles")
def list_deleted_articles():
    """削除済み記事�E管琁E��面"""
    repo = BaseRepository(Article)
    deleted = repo.find_deleted(order_by="deleted_at:desc", limit=100)
    return [
        {
            "id": article.id,
            "title": article.title,
            "deleted_at": article.deleted_at.isoformat(),
        }
        for article in deleted
    ]
```

### 4. ログ記録

削除・復允E��作�Eログに記録します！E

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

### 5. 外部キー制紁E

論理削除を使用する場合、外部キー制紁E�E維持されます！E

```python
class Comment(BaseModelAuto, SoftDeletableMixin):
    __tablename__ = "comments"
    
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    content: Mapped[str] = mapped_column(String)
```

記事が論理削除されても、コメント�E保持されます、E
忁E��に応じて、コメントも連動して論理削除するロジチE��を実裁E��きます、E

---

## トラブルシューチE��ング

### Q: 論理削除非対応モチE��で soft_delete() を呼ぶとエラー

**エラー**:
```
ValueError: MyModel does not support soft delete. Add SoftDeletableMixin to the model.
```

**解決筁E*:
モチE��に `SoftDeletableMixin` を追加してください�E�E

```python
class MyModel(BaseModelAuto, SoftDeletableMixin):
    # ...
```

### Q: find() で削除済みが取得されてしまぁE

**原因**: モチE��ぁE`SoftDeletableMixin` を継承してぁE��ぁE

**確認方況E*:
```python
print(hasattr(MyModel, 'deleted_at'))  # False の場合�E Mixin がなぁE
```

**解決筁E*:
モチE��定義を確認し、`SoftDeletableMixin` を追加してください、E

### Q: 既存データに deleted_at カラムを追加したぁE

**手頁E*:

1. モチE��に Mixin を追加
2. マイグレーションファイル生�E
3. マイグレーション実衁E

```bash
poetry run alembic revision --autogenerate -m "add soft delete"
poetry run alembic upgrade head
```

既存�Eレコード�E `deleted_at = NULL`�E�削除されてぁE��ぁE��として扱われます、E

### Q: 物琁E��除と論理削除を間違えぁE

**論理削除を物琁E��除してしまった場吁E*:
- バックアチE�Eから復允E��る忁E��がありまぁE
- 定期皁E��バックアチE�Eを推奨しまぁE

**物琁E��除すべきところを論理削除してしまった場吁E*:
```python
# 後から物琁E��除できまぁE
repo.permanent_delete(item_id)
```

### Q: パフォーマンスが低下しぁE

**原因**: deleted_at にインチE��クスがなぁE��能性

**確誁E*:
```sql
SHOW INDEX FROM articles WHERE Column_name = 'deleted_at';
```

**解決筁E*:
`SoftDeletableMixin` はチE��ォルトで `index=True` を設定してぁE��すが、E
手動でマイグレーションした場合�EインチE��クスを追加してください�E�E

```python
def upgrade():
    op.create_index('ix_articles_deleted_at', 'articles', ['deleted_at'])
```

---

## 関連ドキュメンチE

- [BaseModelAuto ガイド](base_model_auto_guide.md) - Mixin パターンの詳細
- [BaseRepository ガイド](repository_and_utilities_guide.md) - Repository パターンの詳細
- [Testing ガイド](testing_guide.md) - チE��ト戦略

---

最終更新: 2025-12-10
