"""Application settings loaded from environment variables."""
from __future__ import annotations

from functools import cached_property
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: SecretStr = Field(min_length=32)
    ALLOWED_ORIGINS: str = ""
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    ENV: Literal["dev", "ci", "prod"] = "dev"

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def _origins_no_internal_whitespace(cls, v: str) -> str:
        return v.strip()

    @cached_property
    def allowed_origins_list(self) -> list[str]:
        if not self.ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


def get_settings() -> Settings:
    """Factory. Called inside lifespan / dependencies; overridable in tests."""
    return Settings()
