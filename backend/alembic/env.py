from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (importing registers the tables)
from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The database URL comes from our settings, not from alembic.ini.
config.set_main_option(
    "sqlalchemy.url", settings.sqlalchemy_database_url.replace("%", "%%")
)
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Hide objects that exist only in the database, so autogenerate leaves them alone."""
    if reflected and type_ == "column" and name == "search_vector":
        return False
    if reflected and type_ == "index" and name == "ix_chunks_search_vector":
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=False,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
