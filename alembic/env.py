import pdb
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from repom.db import Base
from repom.config import config as db_config, load_set_model_hook_function

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set runtime database URL from MineDbConfig
# This allows environment-specific databases (dev/test/prod) via EXEC_ENV
config.set_main_option("sqlalchemy.url", db_config.db_url)

# Set version_locations dynamically from MineDbConfig
# This allows external projects to control where migration files are stored
# by inheriting MineDbConfig and setting _alembic_versions_path
config.set_main_option("version_locations", db_config.alembic_versions_path)

# NOTE: We do NOT override script_location here.
# script_location should be set in alembic.ini:
#   - repom standalone: alembic.ini sets "script_location = alembic"
#   - external project: alembic.ini sets "script_location = submod/repom/alembic"
# This prevents path conflicts between repom and consuming applications.

# pdb.set_trace()
# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow applications to import their own models before migrations run.
load_set_model_hook_function()

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
        version_locations=db_config.alembic_versions_path,
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
            version_locations=db_config.alembic_versions_path,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
