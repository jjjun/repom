from repom.database import Base, get_sync_engine
from repom.utility import load_models
from repom.logging import get_logger

logger = get_logger(__name__)


def main():
    load_models(context="db_create")
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database created: {engine.url}")


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
