from repom.database import Base, get_sync_engine
from repom.utility import load_models
from repom.logging import get_logger

logger = get_logger(__name__)


def main():
    load_models(context="db_delete")
    engine = get_sync_engine()
    Base.metadata.drop_all(bind=engine)
    logger.info(f"Database tables dropped: {engine.url}")


if __name__ == "__main__":
    main()
