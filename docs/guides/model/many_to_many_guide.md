# 多対多の関連

`ManyToManyMixin` は、利用側で定義した link model を介して target row に関連付ける
`add_related_item()` を提供します。target row を検索し、必要なら作成し、必要な link row を
追加して target を返します。

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

    removed = account.remove_related_item(
        item_id=tag.id,
        link_model_class=AccountTag,
        self_foreign_key="account_id",
        target_foreign_key="tag_id",
    )
    assert removed is True

    session.commit()
```

`add_related_item()` には、target のデータ、target model class、link model class、link model 上の
owner / target foreign-key attribute 名、既存 row の検索に使う target field を渡します。
instance は SQLAlchemy session に追加され、`id` が設定済みである必要があります。新しい owner
の場合は、この method を呼ぶ前に flush してください。必要に応じて新しい target と link row を
flush しますが、commit はしません。transaction は呼び出し側が管理し、commit または rollback を
決めます。

link row を削除するには、次の method を使います。

`remove_related_item(item_id, link_model_class, self_foreign_key, target_foreign_key) -> bool`

owner と item を結ぶ link row があれば
削除して flush し、`True` を返します。該当する link row がなければ `False` を返します。
target row 自体は削除しません。この method も、instance が session に追加され `id` が設定済みで
あることを必要とし、commit は呼び出し側が行います。
