"""Structured logging configuration.

Uses `structlog` with `contextvars` so context bound at the ASGI boundary
and at command-handler entry propagates to every log line emitted inside
the decider, repository, and projection.

OpenTelemetry trace context (`trace_id`, `span_id`, `trace_flags`) is
injected by the `add_trace_context` processor when an active span is
present, letting log-aggregator queries pivot from a log line to the
corresponding distributed trace. The processor is a no-op when no
span is active (default test environment uses the no-op tracer), so
unit tests don't need to set up a TracerProvider.

The structlog wrapper chain ends with `ProcessorFormatter.wrap_for_formatter`
(not a renderer) so the wrapped event_dict reaches the stdlib
`ProcessorFormatter`, which runs `JSONRenderer()` exactly once. Terminating
the wrapper chain with `JSONRenderer()` would render twice and produce
JSON-in-JSON output that log aggregators can't index.

Caching nuance — `cache_logger_on_first_use=True` means structlog binds
each named logger to its current configuration on first use and ignores
subsequent `configure_logging()` calls for that name. In tests where
`build_kernel()` (which calls `configure_logging()`) runs many
times — once per `create_app()` — only the first call's level/handler
take effect for the rest of the process. Acceptable for our test setup
(everyone uses INFO and the JSONRenderer); breaks if a test tries to
change log level or add a handler mid-process. If we need that flexibility
later, set `cache_logger_on_first_use=False` and accept the per-call
binding cost.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import logging
import sys
from typing import TYPE_CHECKING

import structlog
from structlog.contextvars import merge_contextvars

from cora.infrastructure.observability import add_trace_context

if TYPE_CHECKING:
    from structlog.types import Processor


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog and bridge stdlib logging to it. Call once at startup."""

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Processor] = [
        merge_contextvars,
        add_trace_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Hand off to the stdlib ProcessorFormatter; do not render here.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a logger bound to the given name (typically `__name__`)."""
    return structlog.get_logger(name)
