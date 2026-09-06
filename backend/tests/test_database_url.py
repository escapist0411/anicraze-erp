import pytest

from app.database.url import normalize_database_url


def test_neon_url_is_adapted_for_asyncpg_and_psycopg() -> None:
    config = normalize_database_url(
        "postgresql+asyncpg://demo@ep-example-pooler.ap-southeast-1.aws.neon.tech/"
        "anicraze_demo?sslmode=require&channel_binding=require"
    )

    assert config.runtime_url.drivername == "postgresql+asyncpg"
    assert config.runtime_url.host == "ep-example-pooler.ap-southeast-1.aws.neon.tech"
    assert config.runtime_url.database == "anicraze_demo"
    assert "sslmode" not in config.runtime_url.query
    assert "channel_binding" not in config.runtime_url.query
    assert config.runtime_connect_args == {"ssl": "require"}

    assert config.migration_url.drivername == "postgresql+psycopg"
    assert config.migration_url.query["sslmode"] == "require"
    assert config.migration_url.query["channel_binding"] == "require"


def test_non_ssl_local_postgres_url_remains_supported() -> None:
    config = normalize_database_url("postgresql+asyncpg://postgres@db:5432/anicraze_erp")

    assert config.runtime_connect_args == {}
    assert config.runtime_url.database == "anicraze_erp"


def test_explicit_tls_disable_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not disable PostgreSQL TLS"):
        normalize_database_url("postgresql://user@db.example/app?sslmode=disable")
