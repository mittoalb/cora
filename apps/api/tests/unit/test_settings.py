"""Smoke tests for application Settings loading."""

import pytest

from cora.infrastructure.config import Settings


@pytest.mark.unit
def test_settings_has_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should load with defaults when env vars are unset."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings()

    assert settings.app_env == "local"
    assert settings.log_level == "INFO"
    assert settings.database_url.startswith("postgresql://")


@pytest.mark.unit
def test_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars should override defaults."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@host/db")

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.database_url == "postgresql://test:test@host/db"


@pytest.mark.unit
def test_settings_accepts_postgres_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """asyncpg accepts both 'postgresql://' and 'postgres://'."""
    monkeypatch.setenv("DATABASE_URL", "postgres://test:test@host/db")
    settings = Settings()
    assert settings.database_url == "postgres://test:test@host/db"


@pytest.mark.unit
def test_settings_rejects_malformed_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch typos at startup, not on first connection attempt."""
    import pydantic

    monkeypatch.setenv("DATABASE_URL", "psql://test:test@host/db")
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_rejects_sqlalchemy_style_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SQLAlchemy-style 'postgresql+psycopg2://' URLs aren't supported by asyncpg."""
    import pydantic

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://test:test@host/db")
    with pytest.raises(pydantic.ValidationError):
        Settings()
