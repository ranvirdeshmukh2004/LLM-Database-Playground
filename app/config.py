"""
Application configuration via pydantic-settings.
Reads from environment variables (or .env file).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration in one place."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────
    aurora_url: str = ""

    @property
    def async_database_url(self) -> str:
        if not self.aurora_url:
            raise ValueError("AURORA_URL environment variable is not set")
        return self.aurora_url

    @property
    def database_url(self) -> str:
        return self.async_database_url

    # ── App Secrets ──────────────────────────────────────────
    encryption_key: str = ""
    app_secret_key: str = ""

    # ── Server ───────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 7860
    log_level: str = "info"
    environment: str = "development"

    # ── External Provider Keys (system-level fallback) ───────
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    xai_api_key: str = ""
    openai_api_key: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()
