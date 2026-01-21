# Repository Import Migration Guide

## 📋 概要

repom v2.0 に向けて、リポジトリクラスのインポートパスを変更する必要があります。

### 非推奨となるインポート

```python
# ❌ 非推奨（v2.0 で削除予定）
from repom.base_repository import BaseRepository
from repom.async_base_repository import AsyncBaseRepository
```

### 推奨されるインポート

```python
# ✅ 推奨（v2.0 以降）
from repom import BaseRepository, AsyncBaseRepository

# または
from repom.repositories import BaseRepository, AsyncBaseRepository
```

---

## 🔄 移行手順

### 1. プロジェクト全体での検索

以下のコマンドでプロジェクト内の該当箇所を検索します：

```bash
# PowerShell
Get-ChildItem -Recurse -Include *.py | Select-String "from repom.base_repository import|from repom.async_base_repository import"

# Linux/Mac
grep -r "from repom.base_repository import\|from repom.async_base_repository import" . --include="*.py"
```

### 2. インポート文の書き換え

#### パターン 1: BaseRepository のみ

**変更前:**
```python
from repom.base_repository import BaseRepository
from sqlalchemy.orm import Session

class UserRepository(BaseRepository):
    def __init__(self, session: Session = None):
        super().__init__(User, session)
```

**変更後:**
```python
from repom import BaseRepository
from sqlalchemy.orm import Session

class UserRepository(BaseRepository):
    def __init__(self, session: Session = None):
        super().__init__(User, session)
```

#### パターン 2: AsyncBaseRepository のみ

**変更前:**
```python
from repom.async_base_repository import AsyncBaseRepository
from sqlalchemy.ext.asyncio import AsyncSession

class UserRepository(AsyncBaseRepository):
    def __init__(self, session: AsyncSession = None):
        super().__init__(User, session)
```

**変更後:**
```python
from repom import AsyncBaseRepository
from sqlalchemy.ext.asyncio import AsyncSession

class UserRepository(AsyncBaseRepository):
    def __init__(self, session: AsyncSession = None):
        super().__init__(User, session)
```

#### パターン 3: 複数のクラスをインポート

**変更前:**
```python
from repom.base_repository import BaseRepository, FilterParams
from repom.async_base_repository import AsyncBaseRepository
```

**変更後:**
```python
from repom import BaseRepository, AsyncBaseRepository, FilterParams

# または
from repom.repositories import BaseRepository, AsyncBaseRepository, FilterParams
```

### 3. 一括置換（推奨）

エディタの一括置換機能を使用する場合：

**置換 1:**
```
検索: from repom.base_repository import
置換: from repom import
```

**置換 2:**
```
検索: from repom.async_base_repository import
置換: from repom import
```

### 4. 動作確認

```bash
# テストを実行して動作確認
poetry run pytest

# または特定のテストのみ
poetry run pytest tests/unit_tests/test_repositories.py
```

---

## 📚 詳細な移行例

### 例 1: シンプルなリポジトリ

**変更前:**
```python
# repositories/user_repository.py
from repom.base_repository import BaseRepository
from models.user import User
from sqlalchemy.orm import Session

class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session = None):
        super().__init__(User, session)

    def find_by_email(self, email: str):
        return self.get_by(email=email)
```

**変更後:**
```python
# repositories/user_repository.py
from repom import BaseRepository
from models.user import User
from sqlalchemy.orm import Session

class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session = None):
        super().__init__(User, session)

    def find_by_email(self, email: str):
        return self.get_by(email=email)
```

### 例 2: 非同期リポジトリ

**変更前:**
```python
# repositories/article_repository.py
from repom.async_base_repository import AsyncBaseRepository
from models.article import Article
from sqlalchemy.ext.asyncio import AsyncSession

class ArticleRepository(AsyncBaseRepository[Article]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Article, session)

    async def find_published(self):
        return await self.find_by(status="published")
```

**変更後:**
```python
# repositories/article_repository.py
from repom import AsyncBaseRepository
from models.article import Article
from sqlalchemy.ext.asyncio import AsyncSession

class ArticleRepository(AsyncBaseRepository[Article]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Article, session)

    async def find_published(self):
        return await self.find_by(status="published")
```

### 例 3: FilterParams を使用している場合

**変更前:**
```python
# repositories/user_repository.py
from repom.base_repository import BaseRepository, FilterParams
from models.user import User
from typing import Optional
from pydantic import Field

class UserFilterParams(FilterParams):
    name: Optional[str] = Field(None, description="ユーザー名で検索")
    email: Optional[str] = Field(None, description="メールアドレスで検索")

class UserRepository(BaseRepository[User]):
    filter_params_class = UserFilterParams
    
    field_to_column = {
        'name': User.name,
        'email': User.email,
    }
```

**変更後:**
```python
# repositories/user_repository.py
from repom import BaseRepository, FilterParams
from models.user import User
from typing import Optional
from pydantic import Field

class UserFilterParams(FilterParams):
    name: Optional[str] = Field(None, description="ユーザー名で検索")
    email: Optional[str] = Field(None, description="メールアドレスで検索")

class UserRepository(BaseRepository[User]):
    filter_params_class = UserFilterParams
    
    field_to_column = {
        'name': User.name,
        'email': User.email,
    }
```

---

## ⚠️ 注意事項

### 機能面での変更はなし

この移行は**インポートパスの変更のみ**です。クラスの機能や API に変更はありません。

### 警告メッセージ

移行前は以下のような警告が表示される場合があります：

```
DeprecationWarning: Importing from 'repom.base_repository' is deprecated. 
Use 'from repom import BaseRepository' or 
'from repom.repositories import BaseRepository' instead. 
This import path will be removed in v2.0.
```

移行後はこの警告が表示されなくなります。

### v2.0 でのブレーキングチェンジ

repom v2.0 では、以下のインポートパスが**完全に削除**されます：

- `from repom.base_repository import ...`
- `from repom.async_base_repository import ...`

v2.0 リリース前に必ず移行を完了してください。

---

## 🔍 移行チェックリスト

- [ ] プロジェクト全体で `from repom.base_repository import` を検索
- [ ] プロジェクト全体で `from repom.async_base_repository import` を検索
- [ ] すべてのインポート文を `from repom import` に変更
- [ ] テストを実行して動作確認
- [ ] DeprecationWarning が表示されないことを確認
- [ ] コミット & プッシュ

---

## 📞 サポート

移行時に問題が発生した場合は、以下を確認してください：

1. **repom のバージョン**: `poetry show repom` でバージョンを確認
2. **Python のバージョン**: 3.12+ が必要
3. **テスト実行**: `poetry run pytest` で全テストがパスすることを確認

---

**最終更新**: 2026-01-21  
**対象バージョン**: repom v1.x → v2.0
