"""Database URL adaptation for asynchronous runtime and synchronous migrations."""

from dataclasses import dataclass

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class DatabaseConnectionConfig:
    runtime_url: URL
    migration_url: URL
    runtime_connect_args: dict[str, str]


def normalize_database_url(database_url: str) -> DatabaseConnectionConfig:
    """Derive driver-specific connection settings from one PostgreSQL URL.

    Neon publishes libpq parameters such as ``sslmode`` and
    ``channel_binding``. Psycopg consumes those parameters directly, whereas
    SQLAlchemy's asyncpg dialect forwards them as unsupported keyword
    arguments. Keep them on the migration URL and configure asyncpg TLS via
    its supported ``ssl`` connection argument instead.
    """

    source = make_url(database_url)
    if source.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must use PostgreSQL")

    sslmode = source.query.get("sslmode")
    if isinstance(sslmode, tuple):
        sslmode = sslmode[-1]
    channel_binding = source.query.get("channel_binding")

    runtime_url = source.set(drivername="postgresql+asyncpg").difference_update_query(
        ["sslmode", "channel_binding"]
    )
    migration_url = source.set(drivername="postgresql+psycopg")

    runtime_connect_args: dict[str, str] = {}
    if sslmode:
        if sslmode == "disable":
            raise ValueError("DATABASE_URL must not disable PostgreSQL TLS")
        runtime_connect_args["ssl"] = sslmode
    elif channel_binding:
        # Channel binding requires a protected transport. asyncpg does not
        # implement libpq's channel_binding option, so require TLS explicitly.
        runtime_connect_args["ssl"] = "require"

    return DatabaseConnectionConfig(
        runtime_url=runtime_url,
        migration_url=migration_url,
        runtime_connect_args=runtime_connect_args,
    )
