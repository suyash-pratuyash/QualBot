"""Typed application settings loaded from environment and the project .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Settings required by the Phase 0 FastAPI application."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="QUALBOT_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="QUALBOT_ENV"
    )
    api_prefix: str = Field(default="/api/v1", validation_alias="QUALBOT_API_PREFIX")
    database_url: str = Field(
        default="sqlite:///./qualbot.db", validation_alias="QUALBOT_DATABASE_URL", min_length=1
    )
    cors_origins: Annotated[list[AnyHttpUrl], NoDecode] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:5173")],
        validation_alias="QUALBOT_CORS_ORIGINS",
    )
    frontend_api_base_url: AnyHttpUrl = Field(
        default="http://localhost:8000/api/v1", validation_alias="VITE_API_BASE_URL"
    )

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/api/") or value.endswith("/"):
            raise ValueError("API prefix must start with '/api/' and have no trailing slash")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            url = make_url(value)
        except Exception as exc:
            raise ValueError("Database URL is invalid") from exc
        if url.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError("Database URL must use SQLite or PostgreSQL")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for application startup."""

    return Settings()
