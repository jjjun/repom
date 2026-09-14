import argparse

from repom.database import Base, get_sync_engine, safe_db_url
from repom.utility import load_models
from repom.logging import get_logger
from repom.config import config
from repom.scripts._destructive import confirm_destructive_operation

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Drop every table tracked in Base.metadata for the configured database."
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip the interactive confirmation prompt (required when stdin is not a TTY).",
    )
    args = parser.parse_args()

    confirm_destructive_operation(
        operation="drop all database tables",
        target=safe_db_url(config.db_url),
        exec_env=config.exec_env,
        yes=args.yes,
    )

    load_models(context="db_delete")

    if config.db_type == 'postgres':
        from repom.postgres.manage import ensure_running
        ensure_running()

    engine = get_sync_engine()
    Base.metadata.drop_all(bind=engine)
    logger.info(f"Database tables dropped: {safe_db_url(str(engine.url))}")


if __name__ == "__main__":
    main()
