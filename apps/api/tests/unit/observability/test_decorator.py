"""Unit tests for the `with_tracing` handler-composition wrapper."""

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from cora.infrastructure.observability import with_tracing


@pytest.mark.unit
async def test_creates_one_span_per_call(spans: InMemorySpanExporter) -> None:
    async def handler(value: int) -> int:
        return value * 2

    wrapped = with_tracing(handler, command_name="Double", bc="test")
    result = await wrapped(21)

    assert result == 42
    finished = spans.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].name == "test.command.Double"
    assert finished[0].kind == SpanKind.INTERNAL
    assert finished[0].status.status_code == StatusCode.UNSET


@pytest.mark.unit
async def test_records_cora_namespace_attributes(spans: InMemorySpanExporter) -> None:
    async def handler() -> None:
        return None

    wrapped = with_tracing(handler, command_name="DoThing", bc="myBc")
    await wrapped()

    span = spans.get_finished_spans()[0]
    assert span.attributes is not None
    assert span.attributes.get("cora.bc") == "myBc"
    assert span.attributes.get("cora.command") == "DoThing"


@pytest.mark.unit
async def test_query_kind_uses_query_attribute_and_span_name(
    spans: InMemorySpanExporter,
) -> None:
    async def handler() -> str:
        return "ok"

    wrapped = with_tracing(handler, command_name="GetThing", bc="myBc", kind="query")
    await wrapped()

    span = spans.get_finished_spans()[0]
    assert span.name == "myBc.query.GetThing"
    assert span.attributes is not None
    assert span.attributes.get("cora.query") == "GetThing"
    assert "cora.command" not in span.attributes


@pytest.mark.unit
async def test_records_exception_and_marks_span_error(spans: InMemorySpanExporter) -> None:
    """On exception the span is marked ERROR (so it shows up red in UI)
    AND the exception is recorded as a span event (so the stack appears
    on the trace). Both are needed.

    The exact `status.description` is set by the SDK's record_exception
    helper (typically "ExceptionType: message"); we assert it carries
    the exception class name without locking the format down.
    """

    class BoomError(Exception):
        pass

    async def handler() -> None:
        raise BoomError("blew up")

    wrapped = with_tracing(handler, command_name="Fails", bc="test")

    with pytest.raises(BoomError):
        await wrapped()

    span = spans.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description is not None
    assert "BoomError" in span.status.description
    event_names = [e.name for e in span.events]
    assert "exception" in event_names


@pytest.mark.unit
async def test_preserves_keyword_arguments(spans: InMemorySpanExporter) -> None:
    """ParamSpec-typed wrapper must thread *args and **kwargs faithfully."""
    _ = spans

    async def handler(a: int, *, b: str, c: bool = False) -> tuple[int, str, bool]:
        return (a, b, c)

    wrapped = with_tracing(handler, command_name="Echo", bc="test")
    result = await wrapped(1, b="two", c=True)
    assert result == (1, "two", True)
