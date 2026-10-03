from functools import lru_cache
from typing import Annotated, Literal
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "demo", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )
    debug: bool = False
    app_name: str = "ANICRAZE ERP API"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    storage_backend: Literal["local", "volume"] = Field(default="local", validation_alias="STORAGE_BACKEND")
    storage_root: Path | None = Field(default=None, validation_alias="STORAGE_ROOT")
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "anicraze-erp-api"
    jwt_audience: str = "anicraze-erp-client"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)
    remember_me_refresh_token_expire_days: int = Field(default=30, ge=1, le=180)
    auth_max_login_attempts: int = Field(default=5, ge=1, le=20)
    auth_lock_minutes: int = Field(default=15, ge=1, le=1440)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=1440)
    password_min_length: int = Field(default=8, ge=8, le=128)
    password_max_length: int = Field(default=128, ge=8, le=256)
    expose_dev_reset_token: bool = False
    enable_auth_test_routes: bool = False
    # Support both common loopback spellings used by the local Vite server.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    rate_limit_per_minute: int = Field(default=60, ge=1)
    log_level: str = "INFO"
    whatsapp_enabled: bool = False
    whatsapp_provider: Literal["development", "meta"] = "development"
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_api_version: str = "v23.0"
    whatsapp_invoice_template_name: str = "anicraze_invoice_v1"
    whatsapp_template_language: str = "en"
    whatsapp_max_attempts: int = Field(default=3,ge=1,le=10)
    mail_enabled: bool = False
    mail_provider: Literal["smtp"] = "smtp"
    mail_from: str = "reports@anicraze.local"
    owner_report_email: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587,ge=1,le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    large_stock_adjustment_threshold: int = Field(default=20,ge=1)
    frontend_url: str | None = None
    multi_warehouse_enabled: bool = False
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=5, ge=0, le=20)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "debug", "development"}
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
