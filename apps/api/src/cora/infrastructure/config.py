"""Typed application configuration loaded from environment variables.

`Settings` is loaded once at process start (in `build_shared_deps`) and passed
to adapters that need values from it. Domain and application layers never read
environment variables directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration. Reads from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "local"
    log_level: str = "INFO"

    # Database (Phase 1b will start using this)
    database_url: str = "postgresql://cora:cora@localhost:5432/cora"
