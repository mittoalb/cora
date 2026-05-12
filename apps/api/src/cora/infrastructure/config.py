"""Typed application configuration loaded from environment variables.

`Settings` is loaded once at process start (in `build_kernel`) and passed
to adapters that need values from it. Domain and application layers never read
environment variables directly.
"""

from typing import Literal
from uuid import UUID

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_DATABASE_SCHEMES = ("postgresql://", "postgres://")

OtelExporter = Literal["otlp", "console", "none"]


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

    # HTTP
    # Default 1 MiB. JSON command bodies are tiny (a few hundred bytes
    # at most). The application middleware is defense in depth — production
    # deployments should also configure body limits at the reverse proxy
    # (e.g. nginx `client_max_body_size`) for transport-layer rejection.
    max_request_body_size_bytes: int = 1024 * 1024

    # Observability — OpenTelemetry
    # `none` keeps the global no-op tracer (used by tests so spans don't
    # accumulate across many `create_app()` instances). `console` writes
    # spans to stdout (handy for local dev). `otlp` exports to a
    # collector via the standard `OTEL_EXPORTER_OTLP_*` env vars
    # (we deliberately do NOT shadow them with our own setting so
    # existing OTel deployment tooling Just Works).
    # Resource attribute `service.name` defaults to `cora-api`; override
    # if the same code is deployed under multiple service identities.
    # Sampler ratio is only consulted when otel_exporter == "otlp"; the
    # console exporter always exports every span (development is loud
    # by design). 1.0 = sample everything; lower in high-traffic prod.
    otel_exporter: OtelExporter = "none"
    otel_service_name: str = "cora-api"
    otel_sampler_ratio: float = 1.0

    # Authorization — Trust BC wiring
    # When None, `build_kernel` wires `AllowAllAuthorize` and every
    # command is permitted (Phase 1 default; matches dev/test). When
    # set to a UUID, `TrustAuthorize` is wired and gates every command
    # through that single Policy aggregate. Multi-policy resolution
    # via projections lands in a later phase; until then this is one
    # policy per deployment. Bootstrap workflow (chicken-and-egg with
    # the policy being able to permit DefinePolicy):
    #   1. Start with this unset.
    #   2. POST a permissive policy via /policies; record its id.
    #   3. Restart with this set to that id.
    # See `cora/trust/authorize.py` docstring for the full rationale.
    trust_policy_id: UUID | None = None

    # Production deployments behind an auth proxy that sets
    # `X-Principal-Id` should set this true: requests without the
    # header are then rejected with 401 instead of silently falling
    # back to `SYSTEM_PRINCIPAL_ID`. Default false matches the
    # Phase 1 dev / test posture where the fallback is convenient.
    # The startup check in `create_app()` refuses to boot when
    # `app_env in {"prod", "production"}` and this is False, so a
    # production deployment cannot accidentally launch with the
    # permissive default.
    require_authenticated_principal: bool = False

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

    @field_validator("otel_sampler_ratio")
    @classmethod
    def _validate_otel_sampler_ratio(cls, value: float) -> float:
        """Sampler ratio must be in [0.0, 1.0]; outside that range is meaningless."""
        if not 0.0 <= value <= 1.0:
            msg = f"otel_sampler_ratio must be in [0.0, 1.0], got {value}"
            raise ValueError(msg)
        return value
