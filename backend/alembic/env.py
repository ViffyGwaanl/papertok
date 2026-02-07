from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import settings
from sqlmodel import SQLModel

# Ensure all models are imported so SQLModel.metadata is complete.
from app.models.paper import Paper  # noqa: F401
from app.models.paper_image import PaperImage  # noqa: F401
from app.models.app_setting import AppSetting  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.paper_event import PaperEvent  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
# SQLModel collects all table metadata in SQLModel.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = settings.db_url

    def include_object(object, name, type_, reflected, compare_to):
        # Keep legacy MVP helper tables out of Alembic tracking.
        if type_ == "table" and name in {"schema_version"}:
            return False
        return True

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=False,
        include_object=include_object,
        render_as_batch=("sqlite" in str(url)),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    cfg_section = config.get_section(config.config_ini_section, {})
    cfg_section["sqlalchemy.url"] = settings.db_url

    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        def include_object(object, name, type_, reflected, compare_to):
            if type_ == "table" and name in {"schema_version"}:
                return False
            return True

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
            include_object=include_object,
            render_as_batch=(connection.dialect.name == "sqlite"),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
