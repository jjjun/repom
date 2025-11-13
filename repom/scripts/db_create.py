from repom.db import engine, Base
from repom.config import load_set_model_hook_function


def main():
    load_set_model_hook_function()
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()


"""
指定したモデルのみをデータベースに適用することができます。
これを行うには、特定のモデルの__table__属性を使用して、そのモデルのテーブルを作成します

```
# 指定したモデルのみをデータベースに適用
TaskModel.__table__.create(bind=engine)
PublisherModel.__table__.create(bind=engine)
```
"""
