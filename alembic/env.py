from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from repom.database import Base
from repom.config import config as db_config
from repom.utility import load_models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set runtime database URL from MineDbConfig
# This allows environment-specific databases (dev/test/prod) via EXEC_ENV
config.set_main_option("sqlalchemy.url", db_config.db_url)

# NOTE: version_locations is controlled by alembic.ini only.
# Both file creation (alembic revision) and execution (alembic upgrade)
# use the same location specified in alembic.ini.
#
# Configuration:
#   - repom standalone: version_locations = alembic/versions
#   - external project: version_locations = %(here)s/alembic/versions
#
# script_location should also be set in alembic.ini:
#   - repom standalone: script_location = alembic
#   - external project: script_location = submod/repom/alembic
#
# version_table is read from alembic.ini and defaults to alembic_version.
# version_table_schema is also read from alembic.ini and defaults to None.
# Consumers with multiple independent migration namespaces should give each
# script_location/version_locations pair its own version_table and, when
# separating namespaces by schema, its own version_table_schema.
# During autogenerate, Alembic excludes only the active namespace's version
# table. List sibling namespace version tables in autogenerate_exclude_tables;
# the active version_table does not need to be listed. Do not use this option
# to hide drift in model tables, and carefully review generated migrations.

version_table = config.get_main_option("version_table", "alembic_version")
version_table_schema = config.get_main_option("version_table_schema")
if version_table_schema is not None:
    version_table_schema = version_table_schema.strip() or None


def _parse_table_names(value: str | None) -> frozenset[str]:
    return frozenset(
        name
        for item in (value or "").split(",")
        if (name := item.strip())
    )


autogenerate_exclude_tables = _parse_table_names(
    config.get_main_option("autogenerate_exclude_tables")
)


def include_object(object_, name, type_, reflected, compare_to):
    return not (
        reflected
        and type_ == "table"
        and name in autogenerate_exclude_tables
    )


# pdb.set_trace()
# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow applications to import their own models before migrations run.
load_models(context="alembic_migration")

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=version_table,
        version_table_schema=version_table_schema,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            version_table=version_table,
            version_table_schema=version_table_schema,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
