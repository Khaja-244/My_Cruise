import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models import Base


# Alembic configuration object.
config = context.config


# The project's alembic.ini is intentionally minimal, so only
# configure logging when the required logging sections exist.
if config.config_file_name and config.get_section("loggers"):
    fileConfig(config.config_file_name)


# SQLAlchemy metadata used by Alembic.
target_metadata = Base.metadata


def run_migrations_offline():
    """
    Generate/run migrations without opening a database connection.
    """

    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """
    Configure Alembic and run migrations using a normal
    synchronous SQLAlchemy connection.

    Alembic's migration operations are synchronous, even when
    the application itself uses SQLAlchemy's async engine.
    """

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """
    Connect to PostgreSQL using the application's async database URL.

    The database URL comes directly from settings instead of being
    passed through ConfigParser. This allows passwords containing
    special characters such as '@' to work correctly.
    """

    database_engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    try:
        async with database_engine.connect() as connection:

            # Run the synchronous Alembic migration code inside
            # SQLAlchemy's async-to-sync bridge.
            await connection.run_sync(do_run_migrations)

    finally:
        await database_engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())