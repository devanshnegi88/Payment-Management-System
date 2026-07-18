"""
Application configuration, loaded from environment variables (.env file).

Uses pydantic-settings so config is validated at startup — if a required
variable is missing or the wrong type, the app fails fast with a clear error
instead of failing later with a confusing runtime error.
"""

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App metadata
    APP_NAME: str = "Payout Management System"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str

    # Business rules — kept configurable rather than hardcoded so they can be
    # tuned without code changes, and overridden easily in tests.
    ADVANCE_PAYOUT_PERCENTAGE: float = 10.0
    WITHDRAWAL_COOLDOWN_HOURS: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Singleton settings instance, imported throughout the app.
settings = Settings()
