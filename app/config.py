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

    # ── Database Mode Toggle ────────────────────────────────
    # 'supabase' = Full Supabase stack (GoTrue, Kong, RLS)
    # 'plain'    = Plain PostgreSQL + app-managed auth
    db_mode: str = "supabase"

    @property
    def is_plain_mode(self) -> bool:
        return self.db_mode.lower() == "plain"

    @property
    def is_supabase_mode(self) -> bool:
        return self.db_mode.lower() != "plain"

    # ── PostgreSQL ───────────────────────────────────────────
    postgres_host: str = "supabase-db"
    postgres_port: int = 5432
    postgres_db: str = "postgres"
    postgres_user: str = "postgres"
    postgres_password: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Supabase / JWT ───────────────────────────────────────
    jwt_secret: str = ""
    anon_key: str = ""
    service_role_key: str = ""
    supabase_url: str = "http://supabase-kong:8000"

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

    @property
    def effective_db_host(self) -> str:
        """Return the correct DB host based on mode."""
        return self.postgres_host


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()
