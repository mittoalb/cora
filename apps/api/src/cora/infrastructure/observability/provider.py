"""TracerProvider configuration.

`configure_tracing(settings)` builds a `TracerProvider` with the
exporter, sampler, and resource attributes derived from `Settings`,
installs it as the global provider, and returns a `teardown` callable
that flushes pending spans on shutdown.

Exporter selection (`settings.otel_exporter`):
- `none`   — no provider installed; the global default no-op tracer
  stays active. Used in `app_env=test` so spans don't accumulate
  across many `create_app()` instances in the test process.
- `console`— `ConsoleSpanExporter` with `SimpleSpanProcessor`. Spans
  print to stdout immediately. Local-dev default.
- `otlp`   — `OTLPSpanExporter` (HTTP/protobuf) with
  `BatchSpanProcessor`. Production default; honours the standard
  `OTEL_EXPORTER_OTLP_*` env vars on top of the explicit endpoint.

Sampler is `ParentBased(AlwaysOn)` for `console` (development is
loud by design), and `ParentBased(TraceIdRatioBased(ratio))` for
`otlp` so root spans are sampled at the configured ratio while child
spans inherit the root's sampling decision.

Resource attributes follow OTel semantic conventions:
`service.name`, `service.version`, `service.namespace`,
`deployment.environment`. Set once on the provider; every span
inherits them.
"""

from collections.abc import Callable

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.semconv.attributes.service_attributes import (
    SERVICE_NAME,
    SERVICE_NAMESPACE,
    SERVICE_VERSION,
)

from cora import __version__
from cora.infrastructure.config import Settings

# OTel semconv 0.62b1 has the deployment.environment attribute under a
# pre-stable namespace; pin the literal to avoid breaking when the
# attribute is promoted to stable. The W3C semconv definition is the
# source of truth: deployment.environment.name (1.x) was renamed from
# deployment.environment in 1.27. We use the still-widely-supported
# legacy spelling here — collectors map both.
_DEPLOYMENT_ENVIRONMENT = "deployment.environment"

Teardown = Callable[[], None]


def build_tracing(settings: Settings) -> tuple[TracerProvider | None, Teardown]:
    """Build a TracerProvider per `settings.otel_exporter` without installing it.

    Returns `(provider, teardown)`. `provider` is `None` for `none`
    (no work to do); `teardown` is always callable. Pure: no global
    state mutated, safe to call repeatedly in tests.
    """
    if settings.otel_exporter == "none":
        return None, _noop_teardown

    resource = Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: __version__,
            SERVICE_NAMESPACE: "cora",
            _DEPLOYMENT_ENVIRONMENT: settings.app_env,
        }
    )

    sampler: Sampler
    if settings.otel_exporter == "console":
        sampler = ParentBased(root=ALWAYS_ON)
    else:  # "otlp"
        sampler = ParentBased(root=TraceIdRatioBased(settings.otel_sampler_ratio))

    provider = TracerProvider(resource=resource, sampler=sampler)

    if settings.otel_exporter == "console":
        # SimpleSpanProcessor exports synchronously per finished span —
        # acceptable for local dev where latency doesn't matter and
        # immediate visibility does.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:  # "otlp"
        # BatchSpanProcessor batches spans and flushes asynchronously to
        # the OTLP collector. force_flush() on shutdown drains the queue.
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
            )
        )

    def teardown() -> None:
        # force_flush gives in-flight spans a chance to ship; shutdown
        # tears down processors and exporters cleanly.
        provider.force_flush()
        provider.shutdown()

    return provider, teardown


def configure_tracing(settings: Settings) -> Teardown:
    """Install a global TracerProvider per `settings.otel_exporter`.

    Also instruments process-wide libraries (asyncpg) when tracing is on;
    the asyncpg instrumentor is idempotent (guarded by its own
    `is_instrumented_by_opentelemetry` flag) so calling this from many
    `create_app()` invocations in tests is safe.

    Returns a `teardown()` callable to flush pending spans on shutdown.
    Calling teardown is idempotent and safe even when `none` was selected
    (it returns immediately).

    OTel's `set_tracer_provider` is one-shot per process. If a provider
    is already installed (eg. by an earlier `create_app()` in the test
    suite, or by tests that pre-install their own), the install step is
    skipped — but the new provider still has its teardown wired so
    pending spans flush on shutdown.
    """
    provider, teardown = build_tracing(settings)
    if provider is None:
        return teardown

    if isinstance(trace.get_tracer_provider(), TracerProvider):
        # Pre-existing SDK provider; respect it. The new provider's
        # processors will not see traffic, but its teardown is still
        # safe to call.
        return teardown

    trace.set_tracer_provider(provider)

    # Instrument process-wide libraries. AsyncPGInstrumentor patches the
    # asyncpg module; instrument() is guarded by its own
    # is_instrumented_by_opentelemetry flag so repeat calls (per
    # create_app() in tests) are no-ops.
    AsyncPGInstrumentor().instrument()

    return teardown


def instrument_app(app: FastAPI, settings: Settings) -> None:
    """Attach FastAPIInstrumentor to a specific app instance.

    Per-app (not process-wide) so each `create_app()` in the test suite
    can be cleanly torn down with the app instance. Skipped when tracing
    is off so tests don't pay span-creation overhead.
    """
    if settings.otel_exporter == "none":
        return
    FastAPIInstrumentor.instrument_app(app)


def _noop_teardown() -> None:
    return None
