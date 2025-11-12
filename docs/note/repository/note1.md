# Repository Generics Overview

The shared repository helpers focus on providing type-safe CRUD utilities. The example below illustrates how to declare a repository using Python generics without relying on any application-specific modules.

```python
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy import Column, Integer, String
from mine_db.base_model import BaseModel
from mine_db.base_repository import BaseRepository

T = TypeVar("T", bound=BaseModel)


class TodoModel(BaseModel):
    __tablename__ = "todo_items"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)


class TodoRepository(BaseRepository[TodoModel], Generic[T]):
    def __init__(self, session):
        super().__init__(TodoModel, session)

    def find_by_keyword(self, keyword: Optional[str] = None) -> List[TodoModel]:
        filters = []
        if keyword:
            filters.append(self.model.title.contains(keyword))
        return super().find(filters=filters)
```

`TypeVar(..., bound=BaseModel)` constrains the repository to work only with models that inherit from `BaseModel`. When you pass a different model that does not inherit from `BaseModel`, type checkers will emit errors. The runtime implementation still relies on the underlying SQLAlchemy session.

For repositories that accept any model, you can omit the `bound` argument:

```python
T = TypeVar("T")


class GenericRepository(BaseRepository[T]):
    def __init__(self, model: Type[T], session):
        super().__init__(model, session)
```

Extend these snippets within your application module to build your own domain-specific repositories.
