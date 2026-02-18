"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the TaskFlow API service."""

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    AUTO_CREATE_TABLES: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_FORMAT: Literal["plain", "json"] = "json"
    CORS_ALLOW_ORIGINS: str = "*"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"
    ENABLE_SECURITY_HEADERS: bool = True
    ENABLE_HSTS: bool = False
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_AUTH: str = "20/minute"
    RATE_LIMIT_WRITE: str = "60/minute"
    RATE_LIMIT_READ: str = "240/minute"
    TASK_MAX_PER_USER: int = 500
    BOOTSTRAP_ADMIN_ENABLED: bool = False
    BOOTSTRAP_ADMIN_EMAIL: str | None = None
    BOOTSTRAP_ADMIN_PASSWORD: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
