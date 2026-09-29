"""Typed application settings."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
PROJECT_ROOT=Path(__file__).resolve().parents[3]
class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=PROJECT_ROOT/".env",env_prefix="QUALBOT_",case_sensitive=False,extra="ignore")
    environment: Literal["development","test","production"]="development"
    api_prefix: str="/api/v1"
    database_url: str="sqlite:///./qualbot.db"
    cors_origins: Annotated[list[AnyHttpUrl],NoDecode]=Field(default_factory=lambda:[AnyHttpUrl("http://localhost:5173")])
    frontend_api_base_url: AnyHttpUrl="http://localhost:8000/api/v1"
    gemini_api_key: SecretStr|None=None
    gemini_model: str="gemini-2.5-flash"
    gemini_timeout_seconds: float=8.0
    jwt_secret: str="dev-only-change-this-secret"
    jwt_expiry_seconds: int=3600
    admin_email: str="admin@qualbot.local"
    admin_password: str="qualbot-demo"
    calendly_booking_url: AnyHttpUrl|None=None
    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls,v):
        if not v.startswith("/api/") or v.endswith("/"): raise ValueError("API prefix must start with '/api/' and have no trailing slash")
        return v
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls,v):
        if make_url(v).get_backend_name() not in {"sqlite","postgresql"}: raise ValueError("Database URL must use SQLite or PostgreSQL")
        return v
    @field_validator("cors_origins",mode="before")
    @classmethod
    def split_cors_origins(cls,v):
        return [x.strip() for x in v.split(",") if x.strip()] if isinstance(v,str) else v
    @property
    def gemini_key(self): return self.gemini_api_key.get_secret_value() if self.gemini_api_key else None
@lru_cache(maxsize=1)
def get_settings(): return Settings()
