"""Application settings loaded from environment variables."""
from __future__ import annotations

from functools import cached_property
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str
    SUPABASE_URL: str

    # Auth modes (mutually exclusive in practice; check ordering below):
    #   - HS256 path (legacy / tests): set SUPABASE_JWT_SECRET to the 32+ char shared secret.
    #   - JWKS path (modern Supabase, ES256/RS256 rotatable keys): leave SUPABASE_JWT_SECRET
    #     unset; verify_jwt will fall back to the JWKS document at
    #     {SUPABASE_URL}/auth/v1/.well-known/jwks.json.
    SUPABASE_JWT_SECRET: SecretStr | None = None

    ALLOWED_ORIGINS: str = ""
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    ENV: Literal["dev", "ci", "prod"] = "dev"

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def _origins_no_internal_whitespace(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _jwt_secret_min_length(self) -> Settings:
        if self.SUPABASE_JWT_SECRET is not None:
            value = self.SUPABASE_JWT_SECRET.get_secret_value()
            if len(value) < 32:
                raise ValueError(
                    "SUPABASE_JWT_SECRET must be >= 32 chars when set "
                    "(Supabase HS256 secrets are 40+ chars). "
                    "Unset to use JWKS verification instead."
                )
        return self

    @cached_property
    def allowed_origins_list(self) -> list[str]:
        if not self.ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @cached_property
    def jwks_url(self) -> str:
        """JWKS document URL derived from SUPABASE_URL. Used when SUPABASE_JWT_SECRET is unset."""
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"


def get_settings() -> Settings:
    """Factory. Called inside lifespan / dependencies; overridable in tests."""
    return Settings()
