from repom.database import Base, get_sync_engine
from repom.utility import load_models
from repom.logging import get_logger
from repom.config import config

logger = get_logger(__name__)


def main():
    load_models(context="db_delete")

    if config.db_type == 'postgres':
        from repom.postgres.manage import ensure_running
        ensure_running()

    engine = get_sync_engine()
    Base.metadata.drop_all(bind=engine)
    logger.info(f"Database tables dropped: {engine.url}")


if __name__ == "__main__":
    main()
