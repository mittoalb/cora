"""Per-test span capture against a session-scoped TracerProvider.

OpenTelemetry's `trace.set_tracer_provider` is one-shot per process —
the second call logs "Overriding of current TracerProvider is not
allowed" and silently no-ops. So we install one TracerProvider for the
whole test session and, per test, attach a fresh InMemorySpanExporter
processor to it (then detach on teardown). This is the canonical OTel
test pattern.

`SynchronousMultiSpanProcessor` is the type of `provider._active_span_processor`
when add_span_processor is used. Removing a processor is not part of the
public API; we drive it through the documented private surface
(`shutdown` on the processor + reaching into the active processor's
`_span_processors` list). The alternative — module-reload-per-test — is
heavier and slows the suite by orders of magnitude.
"""

from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import SynchronousMultiSpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _ensure_session_provider() -> TracerProvider:
    """Install a fresh SDK TracerProvider as the global, once per session.

    If something already installed a provider (eg. an earlier test ran
    `configure_tracing`), we reuse that one. Tests must therefore work
    with whatever the global is — they only ever ADD a temporary
    span processor, never replace the provider itself.
    """
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        return current
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    # The second call would warn but we already guarded above.
    return provider


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    """Yield an InMemorySpanExporter attached to the session TracerProvider."""
    provider = _ensure_session_provider()
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    try:
        yield exporter
    finally:
        # Detach by shutting down the processor — SimpleSpanProcessor's
        # shutdown unblocks the worker (no-op for SimpleSpanProcessor) and
        # the SDK won't dispatch new spans to a shutdown processor. We
        # also remove it from the active processor's list so test
        # ordering doesn't accumulate processors across the session.
        processor.shutdown()
        active = provider._active_span_processor  # type: ignore[reportPrivateUsage]
        if isinstance(active, SynchronousMultiSpanProcessor):
            with active._lock:  # type: ignore[reportPrivateUsage]
                processors = active._span_processors  # type: ignore[reportPrivateUsage]
                if processor in processors:
                    active._span_processors = tuple(  # type: ignore[reportPrivateUsage]
                        p for p in processors if p is not processor
                    )
