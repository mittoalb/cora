"""Structured logging configuration.

Uses `structlog` with `contextvars` so context bound at the ASGI boundary
(correlation_id) and at command-handler entry (command_id, decision_id,
aggregate_id, causation_id) propagates to every log line emitted inside the
decider, repository, and projection.

The structlog wrapper chain ends with `ProcessorFormatter.wrap_for_formatter`
(not a renderer) so the wrapped event_dict reaches the stdlib
`ProcessorFormatter`, which runs `JSONRenderer()` exactly once. Terminating
the wrapper chain with `JSONRenderer()` would render twice and produce
JSON-in-JSON output that log aggregators can't index.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import logging
import sys
from typing import TYPE_CHECKING

import structlog
from structlog.contextvars import merge_contextvars

if TYPE_CHECKING:
    from structlog.types import Processor


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog and bridge stdlib logging to it. Call once at startup."""

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Processor] = [
        merge_contextvars,
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
