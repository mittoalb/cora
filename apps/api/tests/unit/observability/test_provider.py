"""Unit tests for `build_tracing` exporter selection.

Tests the pure-build helper rather than `configure_tracing` so we don't
flip the process-global TracerProvider (OTel's `set_tracer_provider` is
one-shot per process; tests that ran it would leak state into others).
The thin install-global wrapper `configure_tracing` is exercised
indirectly by `test_handler_spans_via_testclient.py` via `create_app`.
"""

import pytest
from opentelemetry.sdk.trace import TracerProvider

from cora.infrastructure.config import Settings
from cora.infrastructure.observability import build_tracing


def _settings(**overrides: object) -> Settings:
    """Build a Settings with sensible defaults; overrides merge in."""
    return Settings.model_validate({"app_env": "test", **overrides})


@pytest.mark.unit
def test_none_exporter_returns_no_provider() -> None:
    provider, teardown = build_tracing(_settings(otel_exporter="none"))
    assert provider is None
    teardown()  # callable; must not raise


@pytest.mark.unit
def test_console_exporter_returns_provider_and_callable_teardown() -> None:
    provider, teardown = build_tracing(_settings(otel_exporter="console"))
    assert isinstance(provider, TracerProvider)
    teardown()  # flushes + shuts down without raising


@pytest.mark.unit
def test_otlp_exporter_returns_provider_and_callable_teardown() -> None:
    """No collector running on the test host — but force_flush + shutdown
    must complete without raising on the call thread regardless."""
    provider, teardown = build_tracing(
        _settings(
            otel_exporter="otlp",
            otel_exporter_otlp_endpoint="http://127.0.0.1:65535",
            otel_sampler_ratio=1.0,
        )
    )
    assert isinstance(provider, TracerProvider)
    teardown()
