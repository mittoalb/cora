"""Unit tests for `current_correlation_id`."""

from uuid import UUID

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from cora.infrastructure.observability import current_correlation_id


@pytest.mark.unit
def test_returns_fresh_uuid_when_no_span_active() -> None:
    """Outside any span, a fresh UUIDv4 is generated."""
    cid = current_correlation_id()
    assert isinstance(cid, UUID)


@pytest.mark.unit
def test_returns_distinct_uuids_when_no_span_active() -> None:
    """Successive calls outside a span yield different UUIDs (not constant)."""
    a = current_correlation_id()
    b = current_correlation_id()
    assert a != b


@pytest.mark.unit
def test_derives_uuid_from_active_span_trace_id(spans: InMemorySpanExporter) -> None:
    """Inside a span, the correlation_id encodes the trace_id."""
    _ = spans  # fixture installs the TracerProvider; we don't read exported spans here
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("test-span") as span:
        cid = current_correlation_id()
        trace_id = span.get_span_context().trace_id

    assert cid.int == trace_id


@pytest.mark.unit
def test_same_correlation_id_within_one_span(spans: InMemorySpanExporter) -> None:
    """Two calls inside the same span return the same UUID — useful for
    sanity-checking that the correlation_id is deterministic per request."""
    _ = spans
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("test-span"):
        first = current_correlation_id()
        second = current_correlation_id()

    assert first == second
