"""Unit tests for the `add_trace_context` structlog processor."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from cora.infrastructure.observability import add_trace_context


@pytest.mark.unit
def test_returns_event_dict_unchanged_when_no_span_active() -> None:
    """No span → no trace context added (no None-valued keys polluting indices)."""
    event_dict = {"event": "x", "level": "info"}
    result = add_trace_context(None, "info", event_dict)
    assert result is event_dict
    assert "trace_id" not in result
    assert "span_id" not in result
    assert "trace_flags" not in result


@pytest.mark.unit
def test_injects_trace_context_when_span_active(spans: InMemorySpanExporter) -> None:
    """Inside a span, trace_id (32 hex), span_id (16 hex), and flags are added."""
    _ = spans
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("test-span") as span:
        event_dict: dict[str, object] = {"event": "x", "level": "info"}
        add_trace_context(None, "info", event_dict)
        ctx = span.get_span_context()

    assert event_dict["trace_id"] == format(ctx.trace_id, "032x")
    assert event_dict["span_id"] == format(ctx.span_id, "016x")
    assert event_dict["trace_flags"] == format(ctx.trace_flags, "02x")


@pytest.mark.unit
def test_trace_id_is_lowercase_hex_w3c_format(spans: InMemorySpanExporter) -> None:
    """The trace_id format must match what OTel exporters write (lowercase hex)."""
    _ = spans
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("test-span"):
        event_dict: dict[str, object] = {}
        add_trace_context(None, "info", event_dict)

    trace_id = event_dict["trace_id"]
    assert isinstance(trace_id, str)
    assert len(trace_id) == 32
    assert trace_id == trace_id.lower()
