from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config.settings import get_settings
from app.database.base import Base
from app.database.url import normalize_database_url
from app.models import auth, billing, catalog, crm, hr, inventory, notifications, payables, procurement, reports

config = context.config
settings = get_settings()
database_config = normalize_database_url(settings.database_url)
sync_database_url = database_config.migration_url.render_as_string(hide_password=False)
# ConfigParser treats percent-encoded URL characters as interpolation tokens.
# Escape only for Alembic's INI layer; the direct URL remains unchanged.
config.set_main_option("sqlalchemy.url", sync_database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=sync_database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
