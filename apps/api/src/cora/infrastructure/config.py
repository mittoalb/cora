"""Typed application configuration loaded from environment variables.

`Settings` is loaded once at process start (in `build_shared_deps`) and passed
to adapters that need values from it. Domain and application layers never read
environment variables directly.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_DATABASE_SCHEMES = ("postgresql://", "postgres://")


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

    # Database
    database_url: str = "postgresql://cora:cora@localhost:5432/cora"
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        """Catch malformed DATABASE_URL at startup, not on first asyncpg call."""
        if not value.startswith(_ALLOWED_DATABASE_SCHEMES):
            schemes = " or ".join(_ALLOWED_DATABASE_SCHEMES)
            msg = (
                f"DATABASE_URL must start with {schemes} (got: {value[:40]!r}). "
                "asyncpg accepts both; SQLAlchemy-style 'postgresql+psycopg2://' "
                "URLs are not supported here."
            )
            raise ValueError(msg)
        return value
