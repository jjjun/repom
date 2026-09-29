# Many-to-many relationships

`ManyToManyMixin` provides `add_related_item()` for models that connect to
target rows through an application-defined link model. It finds or creates a
target row, creates the link when needed, and returns the target.

```python
from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from repom import BaseModel
from repom.mixins import ManyToManyMixin


class Account(BaseModel, ManyToManyMixin):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Tag(BaseModel):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)


class AccountTag(BaseModel):
    __tablename__ = "account_tags"

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"))


engine = create_engine("sqlite:///:memory:")
BaseModel.metadata.create_all(engine)

with Session(engine) as session:
    account = Account(name="Example account")
    session.add(account)
    session.flush()

    tag = account.add_related_item(
        data={"name": "Python", "slug": "python"},
        target_model_class=Tag,
        link_model_class=AccountTag,
        self_foreign_key="account_id",
        target_foreign_key="tag_id",
        lookup_fields=["slug"],
    )

    session.commit()
```

`add_related_item()` takes the target data, target model class, link model
class, the owner and target foreign-key attribute names on the link model, and
the target fields used to look up an existing row. The instance must be
attached to a SQLAlchemy session and have a populated `id`; flush a new owner
before calling the method. It flushes new target and link rows as needed but
never commits. The caller owns the transaction and decides whether to commit
or roll it back.
