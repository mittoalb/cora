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


@pytest.mark.unit
def test_settings_trust_policy_id_defaults_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default unset → AllowAllAuthorize wired by build_kernel.
    Phase 1 permissive default; matches dev/test."""
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)
    settings = Settings()
    assert settings.trust_policy_id is None


@pytest.mark.unit
def test_settings_trust_policy_id_parses_uuid_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID

    policy_id = UUID("01900000-0000-7000-8000-000000000601")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))
    settings = Settings()
    assert settings.trust_policy_id == policy_id


@pytest.mark.unit
def test_settings_rejects_malformed_trust_policy_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pydantic UUID validation catches typos at startup."""
    import pydantic

    monkeypatch.setenv("TRUST_POLICY_ID", "not-a-uuid")
    with pytest.raises(pydantic.ValidationError):
        Settings()


@pytest.mark.unit
def test_settings_require_authenticated_principal_defaults_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase-1 dev / test posture: SYSTEM_PRINCIPAL_ID fallback for
    header-less requests is convenient. Production deployments
    explicitly turn this on."""
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)
    settings = Settings()
    assert settings.require_authenticated_principal is False


@pytest.mark.unit
def test_settings_require_authenticated_principal_reads_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")
    settings = Settings()
    assert settings.require_authenticated_principal is True


@pytest.mark.unit
def test_settings_projection_use_listen_notify_default_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROJECTION_USE_LISTEN_NOTIFY", raising=False)
    settings = Settings()
    assert settings.projection_use_listen_notify is True


@pytest.mark.unit
def test_settings_projection_use_listen_notify_can_disable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per `project_deferred.md` NATS trigger: flip to False as an
    interim mitigation before the full NATS bridge ships."""
    monkeypatch.setenv("PROJECTION_USE_LISTEN_NOTIFY", "false")
    settings = Settings()
    assert settings.projection_use_listen_notify is False


@pytest.mark.unit
def test_settings_projection_poll_interval_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROJECTION_POLL_INTERVAL_SECONDS", raising=False)
    settings = Settings()
    assert settings.projection_poll_interval_seconds == 5.0


@pytest.mark.unit
def test_settings_projection_poll_interval_rejects_tight_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Floor of 0.1s prevents accidental tight-loop misconfiguration."""
    import pydantic

    monkeypatch.setenv("PROJECTION_POLL_INTERVAL_SECONDS", "0.05")
    with pytest.raises(pydantic.ValidationError):
        Settings()
