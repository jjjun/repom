from repom.database import Base, get_sync_engine, safe_db_url
from repom.utility import load_models
from repom.logging import get_logger
from repom.config import config

logger = get_logger(__name__)


def main():
    # Strict regardless of config.model_import_strict: create_all against a
    # partial Base.metadata would silently skip creating whichever tables
    # failed to import.
    load_models(context="db_create", strict=True)

    if config.db_type == 'postgres':
        from repom.postgres.manage import ensure_running
        ensure_running()

    engine = get_sync_engine()
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database created: {safe_db_url(str(engine.url))}")


if __name__ == "__main__":
    main()
